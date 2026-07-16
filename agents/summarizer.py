# ================================================================
# File: summarizer.py
# Port: 6003
# Role: 요약 후보 생성 + 단일 패스 파이프라인 조정
# ================================================================

# ============ 표준 라이브러리 및 외부 패키지 임포트 ============
# 비동기 프로그래밍 지원
import asyncio
# 운영체제 관련 기능 (환경변수 읽기 등)
import os
# JSON 데이터 처리
import json
# 단계별 수행시간 측정
import time
# gRPC 라이브러리 (비동기 서버 통신)
import grpc

# ============ Protocol Buffers 생성 파일 임포트 ============
# voc.proto 파일로부터 생성된 메시지 및 서비스 정의
import voc_pb2
import voc_pb2_grpc

# ============ 프로젝트 내부 모듈 임포트 ============
# OpenAI Chat API를 사용하기 위한 래퍼 클래스
from llm_wrappers.generation_factory import make_generation_chat
# Critic에게 사실 확인용 원본 데이터를 함께 보낼 때 쓰는 구분자.
# critic.py 쪽 정의를 그대로 가져와서 두 파일의 문자열이 어긋나지 않게 한다.
from agents.critic import SOURCE_DATA_MARKER


# ============ Summarizer Agent 비즈니스 로직 ============
# VOC 텍스트를 요약하고 여러 후보를 생성하는 에이전트
# ---------------------------------------------------------------
# Summarizer Agent Logic
# ---------------------------------------------------------------
class SummarizerAgent:
    """
    VOC 텍스트를 요약하고 후보(S0,S1,S2...)를 생성하는 agent.
    Refine RPC는 명시적 호출용으로 유지하지만 주 파이프라인은 재생성하지 않는다.
    """

    # ============ 초기화 메서드 ============
    def __init__(self):
        """
        SummarizerAgent 인스턴스를 초기화합니다.
        LLM 래퍼를 인스턴스 변수로 저장하여 재사용합니다.
        """
        # 클래스 변수가 아닌 인스턴스 변수로 생성해야 각 요청마다 독립적인 상태를 유지할 수 있습니다
        self.llm = make_generation_chat("openai")
        # 다음 에이전트 엔드포인트 설정
        self.evaluator_endpoint = os.environ.get("EVALUATOR_ENDPOINT", "localhost:6004")
        # run_pipeline에서 사용하는 에이전트 엔드포인트 설정
        self.retriever_endpoint = os.environ.get("RETRIEVER_ENDPOINT", "localhost:6002")
        self.critic_endpoint = os.environ.get("CRITIC_ENDPOINT", "localhost:6005")
        self.improver_endpoint = os.environ.get("IMPROVER_ENDPOINT", "localhost:6006")

    # ============ 요약 후보 생성 메서드 ============
    async def make_candidates(self, texts: list[str], max_items: int, n: int):
        """
        여러 개의 요약 후보를 생성합니다.
        
        LLM을 사용하여 동일한 VOC 데이터로부터 다양한 관점의 요약을 생성합니다.
        여러 후보를 생성하는 이유: Evaluator가 비교 평가하여 최적의 요약을 선택하기 위함입니다.
        
        Args:
            texts: 요약할 VOC 텍스트 리스트
            max_items: 최대 사용할 텍스트 개수 (메모리 및 토큰 제한 고려)
            n: 생성할 후보 개수 (일반적으로 3개)
            
        Returns:
            dict: 후보 키(S0, S1, S2 등)와 요약 텍스트의 딕셔너리
        """
        # ============ 텍스트 결합 ============
        # 여러 VOC 텍스트를 줄바꿈으로 구분하여 하나의 문자열로 결합합니다
        # max_items 개수만큼만 사용하여 토큰 제한을 준수합니다
        joined = "\n".join(texts[:max_items])

        # ============ 프롬프트 구성 ============
        # LLM에게 요약 후보를 생성하도록 지시하는 프롬프트를 작성합니다
        # 형식: S0, S1, S2 등의 키와 함께 요약을 출력하도록 명시합니다
        # 아래 사실성 제약이 없으면 LLM이 데이터에 없는 구체적 사실·통계를
        # 임의로 지어내는 환각(hallucination) 현상이 발생했다.
        prompt = f"""
다음 VOC 데이터를 읽고 요약 후보를 {n}개 생성해라.

- 아래 데이터에 실제로 있는 내용만 사용해라. 데이터에 없는 구체적 사실, 통계,
  조항명, 수치는 절대 추가하지 마라.
- 여러 건을 하나의 경향으로 종합·일반화하는 것은 괜찮지만, 데이터에 근거 없는
  새로운 내용을 만들어내면 안 된다.

형식:
S0: ...
S1: ...
S2: ...

데이터:
{joined}
"""

        # ============ LLM 호출 ============
        # 비동기로 LLM을 호출하여 요약 후보를 생성합니다
        result = await self.llm(prompt)   
        # ============ 후보 파싱 및 반환 ============
        # LLM 응답에서 후보들을 파싱하여 딕셔너리 형태로 반환합니다
        return self._parse_candidates(result)

    # ============ 요약 개선 메서드 ============
    async def refine(self, draft: str, edits_json: str, texts: list[str] | None = None):
        """
        Critic이 제안한 edits 기반으로 요약문을 개선(refine)합니다.

        Critic이 요약의 품질을 검토하고 수정 지침을 제공하면,
        이 메서드를 사용하여 원본 요약을 개선합니다.

        Args:
            draft: 개선할 원본 요약 텍스트
            edits_json: Critic이 제공한 수정 지침 (JSON 문자열)
            texts: 원본 VOC 텍스트 목록. 있으면 사실성 검증 기준으로 프롬프트에
                포함시켜, "구체화해라" 같은 edits를 반영하다가 원본에 없는
                수치·사례를 지어내는 환각을 막는다. (RunPipeline 경로에서만
                전달되며, 독립 Refine RPC에는 원본 텍스트가 없어 None일 수 있다.)

        Returns:
            str: 개선된 요약 텍스트 (앞뒤 공백 제거)
        """
        # ============ 원본 데이터 근거 블록 구성 ============
        # texts가 있을 때만 사실성 제약을 추가한다. edits를 반영해 "구체화"하다가
        # 원본에 없는 숫자·사례를 지어내는 문제가 있어서, refine 단계에도
        # make_candidates와 동일한 종류의 사실성 제약을 걸어야 했다.
        grounding = ""
        if texts:
            joined = "\n".join(texts)
            grounding = f"""
원본 VOC 데이터(아래 데이터에 실제로 있는 내용만 반영해라. 여기 없는 구체적
사실, 통계, 수치, 사례는 절대 새로 만들어내지 마라):
{joined}
"""

        # ============ 프롬프트 구성 ============
        # 원본 요약과 수정 지침을 포함한 프롬프트를 작성합니다
        # LLM에게 수정 지침에 따라 요약을 개선하도록 지시합니다
        prompt = f"""
아래 draft 요약문을 edits 지시에 따라 개선해라.
{grounding}
draft:
{draft}

edits:
{edits_json}

edits를 반영하되, 원본 데이터에 없는 새로운 사실·통계·수치를 지어내면 안 된다.
더 구체화하라는 지시가 있어도 원본 데이터 안에서만 구체적인 표현을 찾아 써라.
원본에 없으면 없는 대로 두고 억지로 숫자나 사례를 만들어내지 마라.

출력: 개선된 요약문만 제공
"""

        # ============ LLM 호출 및 결과 반환 ============
        # 비동기로 LLM을 호출하여 개선된 요약을 생성합니다
        result = await self.llm(prompt)
        # 앞뒤 공백을 제거하여 깔끔한 텍스트를 반환합니다
        return result.strip()

    # ============ 헬퍼 메서드 ============
    # 내부적으로 사용하는 유틸리티 함수들
    # ----------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------
    def _parse_candidates(self, text: str) -> dict:
        """
        LLM 응답 텍스트에서 요약 후보를 파싱합니다.
        
        LLM이 "S0: ...", "S1: ..." 형식으로 출력한 텍스트에서
        후보 키와 요약 텍스트를 추출하여 딕셔너리로 변환합니다.
        
        Args:
            text: LLM 응답 텍스트
            
        Returns:
            dict: 후보 키(S0, S1 등)와 요약 텍스트의 딕셔너리
                 파싱 실패 시 전체 텍스트를 S0로 반환
        """
        # ============ 줄 단위 분리 ============
        # 텍스트를 줄 단위로 분리하여 각 줄을 처리합니다
        lines = text.split("\n")
        # ============ 후보 딕셔너리 초기화 ============
        out = {}
        # ============ 각 줄 파싱 ============
        # 각 줄에서 "키: 값" 형식을 찾아 후보를 추출합니다
        for line in lines:
            if ":" in line:
                # 콜론을 기준으로 키와 값을 분리합니다
                k, v = line.split(":", 1)  # maxsplit=1로 첫 번째 콜론만 분리
                k = k.strip()  # 키의 앞뒤 공백 제거
                v = v.strip()  # 값의 앞뒤 공백 제거
                # S로 시작하는 키만 후보로 인정합니다 (S0, S1, S2 등)
                if k.startswith("S"):
                    out[k] = v
        # ============ 폴백 처리 ============
        # 파싱된 후보가 없으면 전체 텍스트를 S0로 사용합니다
        if not out:
            out = {"S0": text.strip()}
        # ============ 결과 반환 ============
        return out

    # ============ 전체 요약 파이프라인 실행 메서드 ============
    async def run_pipeline(
        self,
        csv_path: str,
        filters: list[str],
        max_items: int,
        task: str,
        timeout: float = 180.0,
    ) -> dict:
        """
        요약 생성 전체 파이프라인을 실행합니다.
        Retriever, Evaluator, Critic, Improver를 한 번씩 호출하여 결과를 생성합니다.
        
        Args:
            csv_path: CSV 파일 경로
            filters: 필터 키워드 리스트
            max_items: 최대 항목 수
            task: 작업 유형 ("summary", "policy", "both")
            timeout: gRPC 호출 타임아웃
            
        Returns:
            dict: 요약 결과 및 추적 정보
        """
        trace = []
        pipeline_started = time.perf_counter()

        def start_stage(number: int, name: str) -> float:
            print(f"[파이프라인 {number}/6] {name} 진행 중...", flush=True)
            return time.perf_counter()

        def finish_stage(number: int, name: str, started: float) -> float:
            elapsed = time.perf_counter() - started
            print(f"[파이프라인 {number}/6] {name} 완료 ({elapsed:.2f}초)", flush=True)
            trace.append(f"Timing:{name}={elapsed:.2f}s")
            return elapsed
        
        # ============ 1단계: Retriever 호출 ============
        stage_started = start_stage(2, "Retriever")
        async with grpc.aio.insecure_channel(self.retriever_endpoint) as ch:
            stub = voc_pb2_grpc.RetrieverStub(ch)
            rres = await stub.Retrieve(
                voc_pb2.RetrieveReq(
                    csv_path=csv_path,
                    filters=filters,
                    max_items=max_items,
                ),
                timeout=timeout
            )
        finish_stage(2, "Retriever", stage_started)
        texts = list(rres.texts)
        retrieval_preview = " | ".join(text.replace("\n", " ")[:180] for text in texts[:3])
        trace.append(f"Retriever:count={len(texts)},preview={retrieval_preview}")
        
        if not texts:
            total_elapsed = time.perf_counter() - pipeline_started
            print(f"[파이프라인] 검색 결과 없음으로 종료 ({total_elapsed:.2f}초)", flush=True)
            trace.append(f"Timing:AgentPipeline={total_elapsed:.2f}s")
            return {
                "summary": "",
                "trace": "; ".join(trace),
                "ok": False,
            }
        
        # ============ 2단계: 요약 후보 생성 ============
        stage_started = start_stage(3, "Summarizer")
        candidates = await self.make_candidates(texts, max_items, n=3)
        finish_stage(3, "Summarizer", stage_started)
        trace.append(f"Summarizer:candidates={list(candidates.keys())}")
        
        # ============ 3단계: Evaluator 호출 ============
        stage_started = start_stage(4, "Evaluator")
        async with grpc.aio.insecure_channel(self.evaluator_endpoint) as ch:
            stub = voc_pb2_grpc.EvaluatorStub(ch)
            eres = await stub.Evaluate(
                voc_pb2.EvaluateReq(
                    task=task,
                    candidates=candidates
                ),
                timeout=timeout
            )
        finish_stage(4, "Evaluator", stage_started)
        
        winner_key = eres.winner or sorted(candidates.keys())[0]
        summary = candidates.get(winner_key, "")
        eval_json = eres.scores_json or "{}"
        trace.append(f"Evaluator:winner={winner_key}")
        
        # ============ 4단계: Critic 호출 ============
        # 원본 VOC 텍스트(texts)를 구분자와 함께 doc에 실어 보내, Critic이 요약의
        # 사실 왜곡(원본에 없는 통계·사례 등)을 검증할 수 있게 한다. Critic 쪽에서
        # 이 참고 데이터는 Improver 전달·최종 summary에는 남기지 않고 분리한다.
        doc_for_review = summary
        if texts:
            doc_for_review = summary + SOURCE_DATA_MARKER + "\n".join(texts)

        stage_started = start_stage(5, "Critic")
        async with grpc.aio.insecure_channel(self.critic_endpoint) as ch:
            stub = voc_pb2_grpc.CriticStub(ch)
            cres = await stub.Review(
                voc_pb2.ReviewReq(
                    doc=doc_for_review,
                    role="summary"
                ),
                timeout=timeout
            )
        finish_stage(5, "Critic", stage_started)
        
        summary_critic_info = {
            "need_refine": cres.need_refine,
            "edits": list(cres.edits),
            "ask_more_samples": cres.ask_more_samples,
        }
        
        # Critic의 지적은 채점 증적으로 그대로 남기고 요약을 재생성하지 않는다.
        # 테스트 중 발견한 결함을 자동으로 가리지 않기 위한 단일 패스 구조다.
        if cres.need_refine:
            trace.append("Critic:issues_recorded_without_regeneration")

        # ============ 5단계: Improver 정책 개선안 1회 생성 ============
        # Critic의 지적을 이용해 요약을 다시 만들지는 않지만, 다음 단계가 앞 단계
        # 결과를 활용하도록 정책 생성 입력에는 검토 의견을 함께 전달한다.
        improver_input = summary
        if cres.edits or cres.ask_more_samples:
            critic_notes = json.dumps(
                {
                    "검토_의견": list(cres.edits),
                    "추가_표본_필요": cres.ask_more_samples,
                },
                ensure_ascii=False,
            )
            improver_input = f"{summary}\n\n[Critic 검토 결과]\n{critic_notes}"
        stage_started = start_stage(6, "Improver")
        async with grpc.aio.insecure_channel(self.improver_endpoint) as ch:
            stub = voc_pb2_grpc.ImproverStub(ch)
            pres = await stub.Improve(
                voc_pb2.PolicyReq(summary=improver_input),
                timeout=timeout,
            )
        finish_stage(6, "Improver", stage_started)
        policy = pres.policy or ""
        if policy:
            trace.append("Improver:policy_received")

        total_elapsed = time.perf_counter() - pipeline_started
        trace.append(f"Timing:AgentPipeline={total_elapsed:.2f}s")
        print(f"[파이프라인] 6개 에이전트 처리 완료 ({total_elapsed:.2f}초)", flush=True)
        
        return {
            "summary": summary,
            "policy": policy,  # Critic이 Improver로부터 받은 정책 포함
            "eval_json": eval_json,
            "summary_critic_json": json.dumps(summary_critic_info, ensure_ascii=False),
            "trace": "; ".join(trace),
            "ok": True,
        }


# ============ gRPC 서비스 구현 ============
# Protocol Buffers로 정의된 서비스를 구현하는 클래스
# 각 RPC 메서드는 클라이언트의 요청을 받아 비즈니스 로직을 실행합니다
# ---------------------------------------------------------------
# gRPC Servicer
# ---------------------------------------------------------------
class SummarizerServicer(voc_pb2_grpc.SummarizerServicer):
    """
    Summarizer gRPC 서비스를 구현하는 클래스입니다.
    
    voc_pb2_grpc.SummarizerServicer를 상속받아
    Protocol Buffers로 정의된 RPC 메서드들을 구현합니다.
    """

    # ============ 초기화 메서드 ============
    def __init__(self):
        """
        SummarizerServicer 인스턴스를 초기화합니다.
        비즈니스 로직을 담당하는 SummarizerAgent를 생성합니다.
        """
        self.agent = SummarizerAgent()

    # ============ MakeCandidates RPC 구현 ============
    async def MakeCandidates(self, request, context):
        """
        MakeCandidates RPC를 구현합니다.
        
        클라이언트로부터 VOC 텍스트 리스트를 받아
        여러 개의 요약 후보를 생성하고,
        Evaluator를 직접 호출하여 다음 단계로 진행합니다.
        
        Args:
            request: SummarizeReq 메시지 (texts, max_items, n, task 포함)
            context: gRPC 서비스 컨텍스트 (에러 처리 등에 사용)
            
        Returns:
            SummarizeRes: 생성된 후보 딕셔너리를 포함한 응답 메시지
        """
        try:
            # ============ 요약 후보 생성 ============
            # 에이전트의 make_candidates 메서드를 호출하여 후보를 생성합니다
            candidates = await self.agent.make_candidates(
                texts=list(request.texts),      # gRPC repeated 필드를 리스트로 변환
                max_items=request.max_items,    # 최대 항목 수
                n=request.n,                    # 생성할 후보 개수
            )
            
            # ============ Evaluator 직접 호출 ============
            # Summarizer가 Evaluator를 직접 호출하여 다음 단계로 진행합니다
            # Evaluator가 다음 에이전트(Critic)를 호출하므로 여기서는 호출만 수행
            task = getattr(request, 'task', 'both')  # 작업 유형 (proto에 없으면 기본값 사용)
            async with grpc.aio.insecure_channel(self.agent.evaluator_endpoint) as ch:
                stub = voc_pb2_grpc.EvaluatorStub(ch)
                eres = await stub.Evaluate(
                    voc_pb2.EvaluateReq(
                        task=task,
                        candidates=candidates
                    ),
                    timeout=180.0
                )
            # Evaluator가 Critic을 호출하므로 여기서는 결과를 기다리지 않음
            
            # ============ 응답 메시지 생성 및 반환 ============
            # 생성된 후보를 gRPC 응답 메시지로 감싸서 반환합니다
            # (실제로는 Evaluator가 다음 단계를 호출하므로 여기서는 candidates만 반환)
            return voc_pb2.SummarizeRes(candidates=candidates)

        except Exception as e:
            # ============ 에러 처리 ============
            # 예외 발생 시 gRPC 에러로 변환하여 클라이언트에 전달합니다
            await context.abort(
                grpc.StatusCode.INTERNAL,  # 내부 서버 오류 상태 코드
                f"Summarizer.MakeCandidates error: {e}"  # 에러 메시지
            )

    # ============ Refine RPC 구현 ============
    async def Refine(self, request, context):
        """
        Refine RPC를 구현합니다.
        
        클라이언트로부터 원본 요약과 수정 지침을 받아
        개선된 요약을 생성하여 반환합니다.
        
        Args:
            request: RefineReq 메시지 (draft, edits_json 포함)
            context: gRPC 서비스 컨텍스트 (에러 처리 등에 사용)
            
        Returns:
            RefineRes: 개선된 요약 텍스트를 포함한 응답 메시지
        """
        try:
            # ============ 요약 개선 ============
            # 에이전트의 refine 메서드를 호출하여 요약을 개선합니다
            out = await self.agent.refine(
                draft=request.draft,            # 개선할 원본 요약 텍스트
                edits_json=request.edits_json, # 수정 지침 (JSON 문자열)
            )
            # ============ 응답 메시지 생성 및 반환 ============
            # 개선된 요약을 gRPC 응답 메시지로 감싸서 반환합니다
            return voc_pb2.RefineRes(text=out)

        except Exception as e:
            # ============ 에러 처리 ============
            # 예외 발생 시 gRPC 에러로 변환하여 클라이언트에 전달합니다
            await context.abort(
                grpc.StatusCode.INTERNAL,  # 내부 서버 오류 상태 코드
                f"Summarizer.Refine error: {e}"  # 에러 메시지
            )

    # ============ RunPipeline RPC 구현 ============
    async def RunPipeline(self, request, context):
        """
        RunPipeline RPC를 구현합니다.
        
        요약 생성 전체 파이프라인을 실행합니다.
        Retriever, Evaluator, Critic을 직접 호출하여 요약을 생성하고 개선합니다.
        
        Args:
            request: RunPipelineReq 메시지 (csv_path, filters, max_items, task 포함)
            context: gRPC 서비스 컨텍스트 (에러 처리 등에 사용)
            
        Returns:
            RunPipelineRes: 요약 결과 및 추적 정보를 포함한 응답 메시지
        """
        try:
            # ============ 파이프라인 실행 ============
            # 에이전트의 run_pipeline 메서드를 호출하여 전체 파이프라인을 실행합니다
            result = await self.agent.run_pipeline(
                csv_path=request.csv_path,
                filters=list(request.filters),
                max_items=request.max_items,
                task=request.task or "both",
                timeout=180.0,
            )
            # ============ 응답 메시지 생성 및 반환 ============
            # 파이프라인 실행 결과를 gRPC 응답 메시지로 감싸서 반환합니다
            return voc_pb2.RunPipelineRes(
                ok=result.get("ok", False),
                summary=result.get("summary", ""),
                policy=result.get("policy", ""),  # Critic이 Improver로부터 받은 정책 포함
                eval_json=result.get("eval_json", "{}"),
                summary_critic_json=result.get("summary_critic_json", "{}"),
                trace=result.get("trace", ""),
            )

        except Exception as e:
            # ============ 에러 처리 ============
            # 예외 발생 시 gRPC 에러로 변환하여 클라이언트에 전달합니다
            await context.abort(
                grpc.StatusCode.INTERNAL,  # 내부 서버 오류 상태 코드
                f"Summarizer.RunPipeline error: {e}"  # 에러 메시지
            )


# ============ gRPC 서버 실행 함수 ============
# 이 모듈을 직접 실행할 때 gRPC 서버를 시작하는 함수
# ---------------------------------------------------------------
# gRPC Server
# ---------------------------------------------------------------
async def serve():
    """
    Summarizer gRPC 서버를 시작합니다.
    
    환경변수 SUMMARIZER_ENDPOINT에서 엔드포인트를 읽어옵니다.
    기본값은 "0.0.0.0:6003"입니다 (모든 네트워크 인터페이스의 6003 포트).
    """
    # ============ 엔드포인트 설정 ============
    # 환경변수에서 엔드포인트를 읽어오고, 없으면 기본값을 사용합니다
    endpoint = os.environ.get("SUMMARIZER_ENDPOINT", "0.0.0.0:6003")

    # ============ gRPC 서버 생성 ============
    # 비동기 gRPC 서버 인스턴스를 생성합니다
    server = grpc.aio.server()
    # ============ 서비스 등록 ============
    # SummarizerServicer를 서버에 등록하여 RPC 요청을 처리할 수 있도록 합니다
    voc_pb2_grpc.add_SummarizerServicer_to_server(SummarizerServicer(), server)
    # ============ 포트 바인딩 ============
    # 서버를 지정된 엔드포인트에 바인딩합니다 (TLS 없이)
    server.add_insecure_port(endpoint)

    # ============ 서버 시작 로그 ============
    # 서버가 시작되었음을 콘솔에 출력합니다
    print(f"[Summarizer] gRPC server started at {endpoint}")

    # ============ 서버 시작 및 대기 ============
    # 서버를 시작하고 종료 신호를 받을 때까지 대기합니다
    await server.start()
    # 서버가 종료될 때까지 무한 대기합니다 (Ctrl+C로 종료 가능)
    await server.wait_for_termination()


# ============ 메인 실행 블록 ============
# 스크립트가 직접 실행될 때만 서버를 시작합니다
if __name__ == "__main__":
    # asyncio.run()을 사용하여 비동기 서버를 실행합니다
    asyncio.run(serve())
