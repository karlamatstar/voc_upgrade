# ================================================
# File: critic.py
# Role: 요약/정책 비평 에이전트 + gRPC 서버 
# Port (default bind): 0.0.0.0:6005
# ================================================

# ============ 표준 라이브러리 및 타입 힌트 ============
# Python 3.7+ 호환성을 위한 annotations 가져오기
from __future__ import annotations

# 운영체제 관련 기능 (환경변수 읽기 등)
import os
# 비동기 프로그래밍 지원
import asyncio
# 데이터 클래스 정의 (타입 안전한 구조체)
from dataclasses import dataclass
# 타입 힌트를 위한 타입 정의들
from typing import List

# ============ Protocol Buffers 생성 파일 임포트 ============
# voc.proto 파일로부터 생성된 메시지 및 서비스 정의
import grpc
import voc_pb2
import voc_pb2_grpc

# ============ 프로젝트 내부 모듈 임포트 ============
# 요약용 모델 및 OpenAI 클라이언트
from utils.settings import MODEL_SUMMARY, openai_client
# JSON 파싱 유틸리티 함수
from utils.json_utils import safe_json_loads
from llm_wrappers.generation_factory import make_generation_chat


# ============ 비즈니스 로직 ============
# 요약문/정책문을 검토하여 수정 필요 여부와 수정 지침을 생성하는 에이전트
# --------------------------------
# 비즈니스 로직
# --------------------------------

# ============ 사실 확인용 참고 데이터 구분자 ============
# summarizer.py의 RunPipeline이 role="summary" 검토를 요청할 때, 이 구분자
# 뒤에 원본 VOC 데이터를 붙여 doc에 함께 실어 보낸다. Critic은 이 구분자로
# "실제 검토 대상 요약"과 "사실 확인용 참고 데이터"를 분리해서, 참고 데이터는
# 프롬프트에서만 쓰고 Improver 전달·최종 summary에는 새어나가지 않게 한다.
# (이 문자열은 agents/summarizer.py의 값과 반드시 일치해야 한다.)
SOURCE_DATA_MARKER = "\n\n[원본 데이터 - 사실 확인용, 요약에 포함하지 말 것]\n"


# ============ 비평 결과 데이터 클래스 ============
@dataclass
class CriticResult:
    """
    Critic의 검토 결과를 담는 데이터 클래스입니다.
    """
    need_refine: bool      # 개선 필요 여부
    edits: List[str]       # 수정 지침 리스트
    ask_more_samples: bool # 추가 샘플 필요 여부


# ============ Critic 에이전트 클래스 ============
class CriticAgent:
    """
    요약문/정책문을 검토하여 수정 필요 여부와 수정 지침을 생성
    """

    # ============ 초기화 메서드 ============
    def __init__(self, model: str | None = None):
        """
        CriticAgent 인스턴스를 초기화합니다.
        
        Args:
            model: 사용할 OpenAI 모델명 (None이면 settings.MODEL_SUMMARY 사용)
        """
        self.model = model or MODEL_SUMMARY
        self.cross_llm = (
            make_generation_chat("openai", model=model)
            if os.environ.get("GENERATION_PROVIDER")
            else None
        )

    # ============ 문서 검토 메서드 ============
    async def review(self, doc: str, role: str) -> CriticResult:
        """
        요약문 또는 정책 개선안을 검토하여 수정 필요 여부와 수정 지침을 생성합니다.
        
        LLM을 사용하여 문서의 명확성, 일관성, 구체성, 실행 가능성을 평가하고,
        개선이 필요한 경우 구체적인 수정 지침을 제공합니다.
        
        Args:
            doc: 검토할 문서 텍스트 (요약문 또는 정책 개선안)
            role: 문서 역할 ("summary" | "policy")
            
        Returns:
            CriticResult: 검토 결과 (need_refine, edits, ask_more_samples)
            
        Raises:
            RuntimeError: OpenAI 클라이언트가 초기화되지 않았을 때
        """
        # ============ OpenAI 클라이언트 검증 ============
        # OpenAI 클라이언트가 초기화되지 않았으면 에러를 발생시킵니다
        if self.cross_llm is None and openai_client is None:
            raise RuntimeError("OpenAI client is not initialized (check OPENAI_API_KEY)")

        # ============ 역할 설명 결정 ============
        # 역할에 따라 프롬프트에 사용할 설명을 결정합니다
        role_desc = "요약문" if role == "summary" else "정책 개선안"

        # ============ 프롬프트 구성 ============
        # LLM에게 문서를 검토하고 수정 지침을 생성하도록 지시하는 프롬프트를 작성합니다
        # doc 안에 SOURCE_DATA_MARKER가 있으면 그 뒤는 사실 확인용 원본 데이터다.
        # Critic은 이걸로 요약이 실제 데이터에 근거하는지 반드시 검증해야 한다.
        fact_check_instruction = ""
        if SOURCE_DATA_MARKER in doc:
            fact_check_instruction = (
                f'"{SOURCE_DATA_MARKER.strip()}" 아래에 있는 내용은 사실 확인을 위한 '
                "원본 데이터다. [텍스트]의 위쪽(검토 대상)이 이 원본 데이터에 실제로 "
                "근거하는지 반드시 확인해라. 원본 데이터에 없는 구체적 사실, 통계, "
                "수치, 사례가 검토 대상에 있다면, 이는 반드시 need_refine=true와 함께 "
                "edits에 '원본에 없는 사실을 지어냈다'는 취지로 명시해야 한다.\n\n"
            )

        prompt = f"""
다음 {role_desc}를 검토한 뒤, 수정이 필요한지 판단하고 구체적인 수정 지침을 제안해라.
{fact_check_instruction}
[텍스트]
{doc}

반드시 JSON 형식만 출력해라.

{{
  "need_refine": true,
  "edits": [
    "첫 문단에서 불필요한 반복을 줄여라.",
    "구체적인 수치와 사례를 추가해라."
  ],
  "ask_more_samples": false
}}
"""

        # ============ OpenAI API 호출 ============
        # Chat Completions API를 사용하여 문서를 검토합니다
        if self.cross_llm is not None:
            text = await self.cross_llm(
                prompt.strip(),
                max_tokens=int(os.environ.get("CRITIC_MAX_COMPLETION_TOKENS", "500")),
            )
        else:
            resp = await openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "너는 VOC 요약 및 정책 개선안을 검토하는 Critic Agent이다. "
                            "텍스트의 명확성, 일관성, 구체성, 실행 가능성을 기준으로 개선이 필요한지 판단하고 "
                            "JSON 형식으로만 결과를 반환해라."
                        ),
                    },
                    {"role": "user", "content": prompt.strip()},
                ],
                temperature=0.2,
                reasoning_effort=os.environ.get("OPENAI_REASONING_EFFORT", "none"),
                verbosity=os.environ.get("OPENAI_VERBOSITY", "low"),
                max_completion_tokens=int(os.environ.get("CRITIC_MAX_COMPLETION_TOKENS", "500")),
            )
            choice_msg = resp.choices[0].message
            text = getattr(choice_msg, "content", None)
            if text is None and isinstance(choice_msg, dict):
                text = choice_msg.get("content", "")

        # ============ JSON 파싱 ============
        # LLM 응답에서 JSON 블록을 추출하고 파싱합니다
        data = safe_json_loads(text or "") or {}

        # ============ 결과 추출 ============
        # 파싱된 데이터에서 각 필드를 추출합니다
        need_refine = bool(data.get("need_refine", False))  # 개선 필요 여부
        edits = data.get("edits") or []  # 수정 지침 리스트
        # 리스트가 아니면 빈 리스트로 변환
        if not isinstance(edits, list):
            edits = []
        # 모든 편집 지침을 문자열로 변환
        edits = [str(e) for e in edits]

        ask_more = bool(data.get("ask_more_samples", False))  # 추가 샘플 필요 여부

        # ============ 결과 반환 ============
        # 추출한 정보를 CriticResult 객체로 만들어 반환합니다
        return CriticResult(
            need_refine=need_refine,
            edits=edits,
            ask_more_samples=ask_more,
        )


# ============ gRPC 서비스 구현 ============
# Protocol Buffers로 정의된 서비스를 구현하는 클래스
# 클라이언트의 RPC 요청을 받아 CriticAgent의 비즈니스 로직을 실행합니다
# --------------------------------
# gRPC Servicer
# --------------------------------

class CriticServicer(voc_pb2_grpc.CriticServicer):
    """
    Critic gRPC 서비스를 구현하는 클래스입니다.
    
    voc_pb2_grpc.CriticServicer를 상속받아
    Protocol Buffers로 정의된 RPC 메서드들을 구현합니다.
    """
    # ============ 초기화 메서드 ============
    def __init__(self):
        """
        CriticServicer 인스턴스를 초기화합니다.
        비즈니스 로직을 담당하는 CriticAgent를 생성합니다.
        """
        self.critic = CriticAgent()

    # ============ Review RPC 구현 ============
    async def Review(self, request, context):
        """
        Review RPC를 구현합니다.
        
        클라이언트로부터 문서와 역할을 받아 검토 결과만 반환합니다.
        다음 에이전트 호출은 파이프라인 조정자가 담당합니다.
        
        Args:
            request: ReviewReq 메시지 (doc, role 포함)
            context: gRPC 서비스 컨텍스트 (에러 처리 등에 사용)
            
        Returns:
            ReviewRes: 검토 결과를 포함한 응답 메시지
        """
        try:
            role = request.role or "summary"

            # ============ 문서 검토 ============
            # 에이전트의 review 메서드를 호출하여 문서를 검토합니다
            # request.doc에 SOURCE_DATA_MARKER로 원본 데이터가 붙어있으면 그대로
            # 전달해 Critic이 사실 확인을 할 수 있게 한다.
            result: CriticResult = await self.critic.review(
                request.doc,                    # 검토할 문서 텍스트 (+ 사실확인용 원본 데이터)
                role,                           # 문서 역할
            )

            # ============ 참고 데이터 분리 ============
            # Improver 전달과 최종 summary 필드에는 참고 데이터를 빼고
            # 실제 요약(검토 대상)만 사용한다 - 그렇지 않으면 원본 데이터가
            # 정책 생성 입력과 최종 결과에 그대로 섞여 나가게 된다.
            actual_doc = request.doc.split(SOURCE_DATA_MARKER, 1)[0]

            # ============ 응답 메시지 생성 및 반환 ============
            # 검토 결과를 gRPC 응답 메시지로 감싸서 반환합니다
            return voc_pb2.ReviewRes(
                need_refine=result.need_refine,              # 개선 필요 여부
                edits=result.edits,                          # 수정 지침 리스트
                ask_more_samples=result.ask_more_samples,    # 추가 샘플 필요 여부
                policy="",                                # Critic은 검토 결과만 반환
                summary=actual_doc if role == "summary" else "",  # 요약 (role="summary"일 때, 참고 데이터 제외)
            )
        except Exception as e:
            # ============ 에러 처리 ============
            # 예외 발생 시 gRPC 에러로 변환하여 클라이언트에 전달합니다
            await context.abort(grpc.StatusCode.INTERNAL, f"Critic error: {e}")


# ============ gRPC 서버 실행 함수 ============
# 이 모듈을 직접 실행할 때 gRPC 서버를 시작하는 함수
# --------------------------------
# gRPC Server Runner
# --------------------------------

async def serve() -> None:
    """
    Critic gRPC 서버를 시작합니다.
    
    환경변수 CRITIC_BIND에서 엔드포인트를 읽어옵니다.
    기본값은 "0.0.0.0:6005"입니다 (모든 네트워크 인터페이스의 6005 포트).
    """
    # ============ 엔드포인트 설정 ============
    # 환경변수에서 엔드포인트를 읽어오고, 없으면 기본값을 사용합니다
    bind = os.environ.get("CRITIC_BIND", "0.0.0.0:6005")

    # ============ gRPC 서버 생성 ============
    # 비동기 gRPC 서버 인스턴스를 생성합니다
    server = grpc.aio.server()
    # ============ 서비스 등록 ============
    # CriticServicer를 서버에 등록하여 RPC 요청을 처리할 수 있도록 합니다
    voc_pb2_grpc.add_CriticServicer_to_server(CriticServicer(), server)
    # ============ 포트 바인딩 ============
    # 서버를 지정된 엔드포인트에 바인딩합니다 (TLS 없이)
    server.add_insecure_port(bind)

    # ============ 서버 시작 로그 ============
    # 서버가 시작되었음을 콘솔에 출력합니다
    print(f"[Critic] gRPC server started on {bind}")
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
