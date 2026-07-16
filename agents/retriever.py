# =============================================================
# File: retriever.py
# Port: 6002
# Role: VOC CSV에서 필터 기반 단계적 관련성 검색
# =============================================================

# ============ 표준 라이브러리 및 외부 패키지 임포트 ============
# 비동기 프로그래밍 지원
import asyncio
# 운영체제 관련 기능 (파일 존재 여부 확인 등)
import os
# gRPC 라이브러리 (비동기 서버 통신)
import grpc
# CSV 파일 읽기/쓰기 지원
import csv
import re

# ============ Protocol Buffers 생성 파일 임포트 ============
# voc.proto 파일로부터 생성된 메시지 및 서비스 정의
import voc_pb2
import voc_pb2_grpc


# ============ 필터 매칭 헬퍼 ============
_TOKEN_PATTERN = re.compile(r"[가-힣A-Za-z0-9]+")

# 질문 지시어이거나 VOC 전반에 너무 흔해 관련성 판별에 부적합한 단어.
_SEARCH_NOISE = {
    "voc", "데이터", "관련", "현재", "찾아", "찾아서", "고객", "불편", "문제",
    "원인", "공통", "영향", "분석", "정리", "정리해", "정리해주세요", "주세요",
    "개선", "개선안", "방안", "보완", "우선순위", "비교", "비교하고", "정책",
    "처리", "절차", "안내", "설명", "보험", "서비스", "불만", "별로",
    "별로예요", "함께", "때",
}
_AMBIGUOUS_ANCHOR_TERMS = {"서비스"}
_SHORT_DOMAIN_TERMS = {"앱"}
_EMBEDDED_DOMAIN_TERMS = {
    "보험금", "청구", "약관", "거절", "모바일", "앱", "고객센터", "콜센터",
    "사고", "갱신", "환불", "본인", "인증", "납입", "지급", "지연", "대기",
}
_TRAILING_PARTICLES = sorted(
    ["으로부터", "에서부터", "이라도", "라도", "에서", "으로", "에게", "한테", "까지",
     "부터", "이나", "은", "는", "이", "가", "을", "를", "에", "도", "만", "의", "로", "나", "과", "와"],
    key=len,
    reverse=True,
)

# 1차 검색이 0건일 때만 사용하는 제한적 동의어.
_SYNONYM_GROUPS = (
    {"고객센터", "콜센터", "상담센터"},
    {"지연", "대기", "늦음", "늦게"},
    {"모바일", "앱", "애플리케이션"},
    {"불친절", "태도"},
    {"상담원", "상담직원", "직원"},
)


def _meaningful_terms(filters: list[str]) -> list[str]:
    """필터에서 중복과 검색 노이즈를 제거한 핵심어를 뽑는다."""
    terms: list[str] = []
    ambiguous_anchors: list[str] = []

    def add(token: str) -> None:
        if token in _AMBIGUOUS_ANCHOR_TERMS and token not in ambiguous_anchors:
            ambiguous_anchors.append(token)
        if ((len(token) < 2 and token not in _SHORT_DOMAIN_TERMS)
                or token in _SEARCH_NOISE or token in terms):
            return
        terms.append(token)

    for phrase in filters:
        for raw in _TOKEN_PATTERN.findall(phrase.lower()):
            embedded = [term for term in _EMBEDDED_DOMAIN_TERMS if term in raw]
            if embedded and raw not in _EMBEDDED_DOMAIN_TERMS:
                for term in sorted(embedded, key=len, reverse=True):
                    add(term)
                continue

            token = raw
            for particle in _TRAILING_PARTICLES:
                if len(token) > len(particle) and token.endswith(particle):
                    token = token[: -len(particle)]
                    break
            add(token)
    # "서비스가 별로예요"처럼 구체적인 핵심어가 전혀 없는 모호한 질문은
    # 무관한 희소 단어를 쓰지 않고 '서비스'만 최소 앵커로 사용한다. 구체어가
    # 하나라도 있으면 서비스는 다시 범용 노이즈로 취급해 과다매칭을 막는다.
    if not terms and ambiguous_anchors:
        terms.append(ambiguous_anchors[0])
    return terms


def _variants(term: str) -> set[str]:
    """핵심어의 제한적 동의어 집합을 반환한다."""
    for group in _SYNONYM_GROUPS:
        if term in group:
            return group
    return {term}


def _match_count(terms: list[str], line: str, *, synonyms: bool) -> int:
    """행에 일치하는 서로 다른 핵심어 개수를 계산한다."""
    matched_concepts: set[object] = set()
    for term in terms:
        candidates = _variants(term) if synonyms else {term}
        if any(candidate in line for candidate in candidates):
            # 동의어 그룹 안의 두 단어가 필터에 같이 있어도 하나의
            # 의미 개념으로만 세어 일치 점수가 부풀지 않게 한다.
            concept = tuple(sorted(candidates)) if synonyms else term
            matched_concepts.add(concept)
    return len(matched_concepts)


def _required_match_count(term_count: int) -> int:
    """1차 검색의 최소 핵심어 일치 개수를 결정한다."""
    if term_count <= 1:
        return 1
    if term_count <= 4:
        return 2
    return 3


# ============ Retriever Agent 비즈니스 로직 ============
# CSV 파일에서 필터 조건에 맞는 VOC 데이터를 검색하는 에이전트
# 1차 정확 검색 → 2차 제한 완화 → 관련 데이터 없음 순으로 검색합니다.
# -------------------------------------------------------------
# Retriever Agent Logic (단계적 관련성 검색)
# -------------------------------------------------------------
class RetrieverAgent:
    """
    filters 기반으로 VOC CSV에서 관련성 높은 텍스트를 추출하는 Agent.
    필터 검색은 관련성 상위 10건까지만 반환한다.
    """

    # ============ 초기화 메서드 ============
    def __init__(self):
        """
        RetrieverAgent 인스턴스를 초기화합니다.
        다음 에이전트(Summarizer)의 엔드포인트를 설정합니다.
        """
        # ============ 다음 에이전트 엔드포인트 설정 ============
        # Summarizer 에이전트의 엔드포인트를 환경변수에서 읽어옵니다
        self.summarizer_endpoint = os.environ.get("SUMMARIZER_ENDPOINT", "localhost:6003")

    # ============ 검색 실행 메서드 ============
    async def run(self, csv_path: str, filters: list[str], max_items: int) -> list[str]:
        """
        CSV 파일에서 필터 조건에 맞는 VOC 텍스트를 검색합니다.
        
        1차 핵심어 복수 일치를 우선하고, 0건일 때만 동의어와
        희소 구체어를 이용한 제한적 2차 검색을 시도합니다.
        
        Args:
            csv_path: 검색할 CSV 파일 경로
            filters: 필터링할 키워드 리스트 (빈 리스트면 필터링 없음)
            max_items: 최대 반환할 항목 수 (1~500 범위로 제한)
            
        Returns:
            list[str]: 검색된 VOC 텍스트 리스트
            
        Raises:
            FileNotFoundError: CSV 파일이 존재하지 않을 때
        """
        # ============ CSV 파일 존재 여부 확인 ============
        # 파일이 없으면 조기 종료하여 불필요한 처리를 방지합니다
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"CSV not found: {csv_path}")

        # ============ 필터 전처리 ============
        # 필터 키워드들을 소문자로 변환하고 앞뒤 공백을 제거합니다
        # 빈 문자열은 제외합니다
        filters = [f.lower().strip() for f in (filters or []) if f.strip()]

        # ============ 필터 사용 여부 결정 ============
        # 빈 필터 리스트는 필터링을 사용하지 않음을 의미합니다
        # 전체 반환 모드가 아니라 필터가 없으면 모든 행을 반환합니다
        use_filter = len(filters) > 0

        # ============ max_items 검증 및 제한 ============
        # max_items를 정수로 변환하고 유효한 범위로 제한합니다
        try:
            max_items = int(max_items)
        except Exception:
            # 변환 실패 시 기본값 사용
            max_items = 30

        # ============ 범위 제한 ============
        # 최소값: 30 (0 이하일 때)
        if max_items <= 0:
            max_items = 30
        # 최대값: 500 (너무 많은 항목 반환 방지)
        if max_items > 500:
            max_items = 500

        # ============ 결과 리스트 초기화 ============
        result_limit = min(max_items, 10) if use_filter else max_items
        results: list[str] = []
        # 필터를 쓸 때는 (매칭된 필터 개수, 원본 행)을 모아뒀다가 관련성 순으로
        # 정렬한다. 예전에는 CSV에 먼저 나온 순서로만 max_items를 채워서, 필터
        # 1개만 겹치는 낮은 관련성 항목이 필터 여러 개가 겹치는 항목보다 먼저
        # 포함되는 문제가 있었다(예: 팩스 질문에 이메일 사례가 섞여 들어감).
        rows: list[tuple[str, str]] = []

        # ============ CSV 파일 읽기 및 필터링 ============
        # UTF-8 인코딩으로 CSV 파일을 열어 한글을 올바르게 처리합니다
        with open(csv_path, "r", encoding="utf-8-sig") as fp:
            csv_reader = csv.reader(fp)
            next(csv_reader, None)  # 헤더는 VOC 검색 대상에서 제외
            # ============ 각 행 처리 ============
            for row in csv_reader:
                # ============ 행을 문자열로 변환 ============
                # CSV의 각 열을 공백으로 결합하여 하나의 문자열로 만듭니다
                # 소문자로 변환하여 대소문자 구분 없이 검색합니다
                line = " ".join(row).lower()

                if not use_filter:
                    # 필터가 없으면 예전과 동일하게 CSV 순서대로 max_items까지 채운다
                    results.append(" ".join(row))
                    if len(results) >= result_limit:
                        break
                    continue

                # 같은 CSV를 1차 원문 검색과 2차 동의어 검색에 공통으로 사용한다.
                rows.append((line, " ".join(row)))

        if use_filter:
            # 고객·문제·개선 같은 범용어를 제거한 핵심어로 1차 정확 검색한다.
            terms = _meaningful_terms(filters)
            if not terms:
                return []

            strict_threshold = _required_match_count(len(terms))
            strict = [
                (_match_count(terms, line, synonyms=False), text)
                for line, text in rows
            ]
            strict = [item for item in strict if item[0] >= strict_threshold]

            # 1차가 0건일 때만 제한적 동의어로 2차 검색한다. 기준 미달 결과는 되살리지 않는다.
            if strict:
                selected = strict
            else:
                relaxed_threshold = 1 if len(terms) == 1 else 2
                selected = [
                    (_match_count(terms, line, synonyms=True), text)
                    for line, text in rows
                ]
                selected = [item for item in selected if item[0] >= relaxed_threshold]

                if not selected and rows:
                    # 여러 세부 주제가 서로 다른 VOC 행에 나뉘어 있으면 복수 일치가
                    # 불가능할 수 있다. CSV 전체의 15% 이하에만 나오는 드문 핵심어는
                    # 한 개 일치도 허용하되, 흔한 단어는 이 완화를 받지 못한다.
                    frequencies = {
                        term: sum(
                            any(candidate in line for candidate in _variants(term))
                            for line, _ in rows
                        )
                        for term in terms
                    }
                    # '게임+아이템+환불'처럼 핵심 주제어 여러 개가 CSV에 전혀
                    # 없으면, 드문 '환불' 하나만으로 다른 주제를 가져오지 않는다.
                    if sum(frequency == 0 for frequency in frequencies.values()) < 2:
                        rare_terms = {
                            term
                            for term, frequency in frequencies.items()
                            if 0 < frequency / len(rows) <= 0.15
                        }
                        selected = [
                            (_match_count(terms, line, synonyms=True), text)
                            for line, text in rows
                            if any(
                                candidate in line
                                for term in rare_terms
                                for candidate in _variants(term)
                            )
                        ]

            selected.sort(key=lambda item: item[0], reverse=True)
            results = [text for _, text in selected[:result_limit]]

        # ============ 결과 반환 ============
        return results


# ============ gRPC 서비스 구현 ============
# Protocol Buffers로 정의된 서비스를 구현하는 클래스
# 클라이언트의 RPC 요청을 받아 RetrieverAgent의 비즈니스 로직을 실행합니다
# -------------------------------------------------------------
# gRPC Servicer
# -------------------------------------------------------------
class RetrieverServicer(voc_pb2_grpc.RetrieverServicer):
    """
    Retriever gRPC 서비스를 구현하는 클래스입니다.
    
    voc_pb2_grpc.RetrieverServicer를 상속받아
    Protocol Buffers로 정의된 RPC 메서드들을 구현합니다.
    """

    # ============ 초기화 메서드 ============
    def __init__(self):
        """
        RetrieverServicer 인스턴스를 초기화합니다.
        비즈니스 로직을 담당하는 RetrieverAgent를 생성합니다.
        """
        self.agent = RetrieverAgent()

    # ============ Retrieve RPC 구현 ============
    async def Retrieve(self, request, context):
        """
        Retrieve RPC를 구현합니다.
        
        클라이언트로부터 CSV 경로, 필터, 최대 항목 수를 받아
        필터 조건에 맞는 VOC 텍스트를 검색하고,
        Summarizer를 직접 호출하여 다음 단계로 진행합니다.
        
        Args:
            request: RetrieveReq 메시지 (csv_path, filters, max_items, task 포함)
            context: gRPC 서비스 컨텍스트 (에러 처리 등에 사용)
            
        Returns:
            RetrieveRes: 검색된 텍스트 리스트를 포함한 응답 메시지
        """
        try:
            # ============ 요청 파라미터 추출 ============
            csv_path = request.csv_path        # CSV 파일 경로
            filters = list(request.filters)    # 필터 키워드 리스트 (gRPC repeated 필드를 리스트로 변환)
            max_items = request.max_items       # 최대 검색 항목 수
            task = getattr(request, 'task', 'both')  # 작업 유형 (proto에 없으면 기본값 사용)

            # ============ 검색 실행 ============
            # 에이전트의 run 메서드를 호출하여 VOC 데이터를 검색합니다
            texts = await self.agent.run(csv_path, filters, max_items)

            # ============ Summarizer 직접 호출 ============
            # Retriever가 Summarizer를 직접 호출하여 다음 단계로 진행합니다
            async with grpc.aio.insecure_channel(self.agent.summarizer_endpoint) as ch:
                stub = voc_pb2_grpc.SummarizerStub(ch)
                sres = await stub.MakeCandidates(
                    voc_pb2.SummarizeReq(
                        texts=texts,
                        max_items=max_items,
                        n=3,
                    ),
                    timeout=180.0
                )
            
            # ============ 응답 메시지 생성 및 반환 ============
            # 검색된 텍스트를 gRPC 응답 메시지로 감싸서 반환합니다
            # (실제로는 Summarizer가 다음 단계를 호출하므로 여기서는 texts만 반환)
            return voc_pb2.RetrieveRes(texts=texts)

        except Exception as e:
            # ============ 에러 처리 ============
            # 예외 발생 시 gRPC 에러로 변환하여 클라이언트에 전달합니다
            await context.abort(
                grpc.StatusCode.INTERNAL,  # 내부 서버 오류 상태 코드
                f"Retriever error: {e}"   # 에러 메시지
            )


# ============ gRPC 서버 실행 함수 ============
# 이 모듈을 직접 실행할 때 gRPC 서버를 시작하는 함수
# -------------------------------------------------------------
# gRPC Server
# -------------------------------------------------------------
async def serve():
    """
    Retriever gRPC 서버를 시작합니다.
    
    환경변수 RETRIEVER_ENDPOINT에서 엔드포인트를 읽어옵니다.
    기본값은 "0.0.0.0:6002"입니다 (모든 네트워크 인터페이스의 6002 포트).
    """
    # ============ 엔드포인트 설정 ============
    # 환경변수에서 엔드포인트를 읽어오고, 없으면 기본값을 사용합니다
    endpoint = os.environ.get("RETRIEVER_ENDPOINT", "0.0.0.0:6002")

    # ============ gRPC 서버 생성 ============
    # 비동기 gRPC 서버 인스턴스를 생성합니다
    server = grpc.aio.server()
    # ============ 서비스 등록 ============
    # RetrieverServicer를 서버에 등록하여 RPC 요청을 처리할 수 있도록 합니다
    voc_pb2_grpc.add_RetrieverServicer_to_server(RetrieverServicer(), server)
    # ============ 포트 바인딩 ============
    # 서버를 지정된 엔드포인트에 바인딩합니다 (TLS 없이)
    server.add_insecure_port(endpoint)

    # ============ 서버 시작 로그 ============
    # 서버가 시작되었음을 콘솔에 출력합니다
    print(f"[Retriever] gRPC server started at {endpoint}")

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
