param(
    [string]$Root = "D:\voc"
)

$ErrorActionPreference = "Stop"
$reports = Join-Path $Root "quality_diagnosis\reports"
$assets = Join-Path $reports "report_assets"
$judgeLog = Join-Path $reports "logs\llm_judge\llm_judge_20260715_143539_908132.json"
$pytestLog = Join-Path $reports "logs\pytest\pytest_20260715_142539_267083.json"
$judgeCsv = Join-Path $reports "llm_judge_result.csv"
$scoreMd = Join-Path $reports "quality_score_report.md"
$casesJson = Join-Path $Root "quality_diagnosis\test_cases.json"

foreach ($path in @($judgeLog, $pytestLog, $judgeCsv, $scoreMd, $casesJson)) {
    if (-not (Test-Path -LiteralPath $path)) { throw "필수 보고서 자료가 없습니다: $path" }
}

$judge = Get-Content -LiteralPath $judgeLog -Raw -Encoding UTF8 | ConvertFrom-Json
$pytest = Get-Content -LiteralPath $pytestLog -Raw -Encoding UTF8 | ConvertFrom-Json
$rows = @(Import-Csv -LiteralPath $judgeCsv -Encoding UTF8)
$caseDefs = (Get-Content -LiteralPath $casesJson -Raw -Encoding UTF8 | ConvertFrom-Json).cases

if ($judge.status -ne "completed") { throw "LLM Judge 실행이 완료 상태가 아닙니다: $($judge.status)" }
if ($pytest.status -ne "completed") { throw "pytest 실행이 완료 상태가 아닙니다: $($pytest.status)" }
if ([int]$judge.case_counts.processed -ne 18) { throw "Judge 처리 건수가 18건이 아닙니다." }

New-Item -ItemType Directory -Path $assets -Force | Out-Null

function ConvertTo-HtmlText([object]$value) {
    return [System.Net.WebUtility]::HtmlEncode([string]$value)
}

function HtmlTable([string[]]$headers, [object[]]$tableRows, [string]$class = "data") {
    $sb = [System.Text.StringBuilder]::new()
    [void]$sb.Append("<table class='$class'><thead><tr>")
    foreach ($header in $headers) { [void]$sb.Append("<th>$(ConvertTo-HtmlText $header)</th>") }
    [void]$sb.Append("</tr></thead><tbody>")
    foreach ($row in $tableRows) {
        [void]$sb.Append("<tr>")
        foreach ($cell in $row) { [void]$sb.Append("<td>$(ConvertTo-HtmlText $cell)</td>") }
        [void]$sb.Append("</tr>")
    }
    [void]$sb.Append("</tbody></table>")
    return $sb.ToString()
}

function FileUrl([string]$path) {
    return "file:///" + ($path -replace '\\', '/')
}

Add-Type -AssemblyName System.Windows.Forms.DataVisualization
Add-Type -AssemblyName System.Drawing

function New-BarChart {
    param(
        [string]$Path,
        [string]$Title,
        [string[]]$Labels,
        [double[]]$Values,
        [double]$Maximum = 0,
        [string]$Color = "#2673B8",
        [string]$ValueSuffix = ""
    )
    $chart = [System.Windows.Forms.DataVisualization.Charting.Chart]::new()
    $chart.Width = 1200
    $chart.Height = [Math]::Max(620, 70 * $Labels.Count + 180)
    $chart.BackColor = [System.Drawing.Color]::White
    $area = [System.Windows.Forms.DataVisualization.Charting.ChartArea]::new("Main")
    $area.BackColor = [System.Drawing.Color]::White
    $area.AxisX.Interval = 1
    $area.AxisX.IsReversed = $true
    $area.AxisX.LabelStyle.Font = [System.Drawing.Font]::new("맑은 고딕", 11)
    $area.AxisY.LabelStyle.Font = [System.Drawing.Font]::new("맑은 고딕", 10)
    $area.AxisX.MajorGrid.Enabled = $false
    $area.AxisY.MajorGrid.LineColor = [System.Drawing.Color]::FromArgb(225, 231, 239)
    if ($Maximum -gt 0) { $area.AxisY.Maximum = $Maximum }
    [void]$chart.ChartAreas.Add($area)
    $series = [System.Windows.Forms.DataVisualization.Charting.Series]::new("Value")
    $series.ChartType = [System.Windows.Forms.DataVisualization.Charting.SeriesChartType]::Bar
    $series.Color = [System.Drawing.ColorTranslator]::FromHtml($Color)
    $series.IsValueShownAsLabel = $false
    $series.Font = [System.Drawing.Font]::new("맑은 고딕", 10, [System.Drawing.FontStyle]::Bold)
    for ($i = 0; $i -lt $Labels.Count; $i++) {
        $point = [System.Windows.Forms.DataVisualization.Charting.DataPoint]::new()
        $point.SetValueY([double]$Values[$i])
        $point.AxisLabel = $Labels[$i]
        $point.Label = ("{0:0.##}{1}" -f [double]$Values[$i], $ValueSuffix)
        [void]$series.Points.Add($point)
    }
    [void]$chart.Series.Add($series)
    $titleObj = [System.Windows.Forms.DataVisualization.Charting.Title]::new($Title)
    $titleObj.Font = [System.Drawing.Font]::new("맑은 고딕", 16, [System.Drawing.FontStyle]::Bold)
    [void]$chart.Titles.Add($titleObj)
    $chart.SaveImage($Path, [System.Windows.Forms.DataVisualization.Charting.ChartImageFormat]::Png)
    $chart.Dispose()
}

function New-DonutChart {
    param(
        [string]$Path,
        [string]$Title,
        [string[]]$Labels,
        [double[]]$Values,
        [string[]]$Colors
    )
    $chart = [System.Windows.Forms.DataVisualization.Charting.Chart]::new()
    $chart.Width = 1000
    $chart.Height = 650
    $chart.BackColor = [System.Drawing.Color]::White
    $area = [System.Windows.Forms.DataVisualization.Charting.ChartArea]::new("Main")
    $area.BackColor = [System.Drawing.Color]::White
    [void]$chart.ChartAreas.Add($area)
    $series = [System.Windows.Forms.DataVisualization.Charting.Series]::new("Value")
    $series.ChartType = [System.Windows.Forms.DataVisualization.Charting.SeriesChartType]::Doughnut
    $series["DoughnutRadius"] = "55"
    $series["PieLabelStyle"] = "Outside"
    $series.Font = [System.Drawing.Font]::new("맑은 고딕", 11, [System.Drawing.FontStyle]::Bold)
    for ($i = 0; $i -lt $Labels.Count; $i++) {
        $point = [System.Windows.Forms.DataVisualization.Charting.DataPoint]::new()
        $point.SetValueY([double]$Values[$i])
        $point.LegendText = "$($Labels[$i]) ($($Values[$i]))"
        $point.Label = "$($Values[$i])"
        $point.Color = [System.Drawing.ColorTranslator]::FromHtml($Colors[$i])
        [void]$series.Points.Add($point)
    }
    [void]$chart.Series.Add($series)
    $legend = [System.Windows.Forms.DataVisualization.Charting.Legend]::new("Legend")
    $legend.Docking = [System.Windows.Forms.DataVisualization.Charting.Docking]::Bottom
    $legend.Font = [System.Drawing.Font]::new("맑은 고딕", 11)
    [void]$chart.Legends.Add($legend)
    $titleObj = [System.Windows.Forms.DataVisualization.Charting.Title]::new($Title)
    $titleObj.Font = [System.Drawing.Font]::new("맑은 고딕", 16, [System.Drawing.FontStyle]::Bold)
    [void]$chart.Titles.Add($titleObj)
    $chart.SaveImage($Path, [System.Windows.Forms.DataVisualization.Charting.ChartImageFormat]::Png)
    $chart.Dispose()
}

$scored = @($rows | Where-Object { $_.total -match '^\d+(\.\d+)?$' })
$noData = @($rows | Where-Object { $_.verdict -eq 'PASS (예외처리)' })
$immediate = @($scored | Where-Object { $_.immediate_hold -match 'true' })
$average = [Math]::Round((($scored | ForEach-Object { [double]$_.total }) | Measure-Object -Average).Average, 1)
$limitedCases = @($scored | Where-Object { $_.rationale -match '표본|대표성.*부족|검색.*[012]건' })

$metricMax = [ordered]@{
    'Interpreter 해석 정확성' = 15
    'Retriever 검색 관련성' = 15
    'Summarizer 사실성·요약성' = 15
    'Evaluator 평가 타당성' = 10
    'Critic 위험 탐지력' = 10
    'Improver 실행 가능성' = 15
    'Agent 연계 품질' = 10
    '장애 대응·로그' = 5
    '성능' = 5
}
$metricStats = @(
    foreach ($name in $metricMax.Keys) {
        $values = @($scored | ForEach-Object { [double]($_.$name) })
        $avg = ($values | Measure-Object -Average).Average
        [pscustomobject]@{
            Name = $name
            Average = [Math]::Round($avg, 2)
            Max = $metricMax[$name]
            Percent = [Math]::Round(($avg / $metricMax[$name]) * 100, 1)
        }
    }
)

$verdictOrder = @('조건부 배포 가능, 개선 후 재검증', '주요 개선 필요', '배포 보류', '배포 보류(즉시)')
$verdictShort = @('조건부 배포', '주요 개선', '배포 보류', '즉시 보류')
$verdictCounts = @(
    foreach ($verdict in $verdictOrder) { @($scored | Where-Object { $_.verdict -eq $verdict }).Count }
)

$testSummary = @{
    'test_agent_unit.py' = '6개 에이전트(Interpreter/Retriever/Summarizer/Evaluator/Critic/Improver) 파일 존재·문법·필수 심볼·main 진입점을 각각 확인(4종×6=24) 후 포트 중복 없음, voc.csv 존재·데이터, proto 6개 서비스, 권장 케이스 기대 결과 구조를 검증'
    'test_fault_tolerance.py' = 'CSV 정상·누락 상태, 빈 질문, 불용어 제거, None 필터, 서버 중단, Summarizer 가동 중 장애 시나리오, 데이터 파일 오류가 성공으로 숨겨지지 않는지 검증'
    'test_llm_judge.py' = '100점 배점·9개 항목, 케이스 로드, 프롬프트 입력, Judge JSON 파싱·점수 상한·비정상 응답, 점수 구간별 판정·즉시 보류, 모듈 import를 검증'
    'test_llm_retry.py' = '3회째 성공, 3회 모두 실패 기록, 인증 오류의 즉시 중단, API 실패 N/A를 평균에서 제외하는지 검증'
    'test_mcp_tools.py' = 'MCP 인스턴스·필수 3개·선택 2개 도구 등록, main.py stdio 진입점, health_check 호출, 파라미터·자연어 VOC 분석 E2E를 검증'
    'test_pipeline_e2e.py' = '파라미터 기반 스모크, 요약+개선안 전체 작업, trace에 6개 에이전트 연계가 남는지 실제 API 파이프라인으로 검증'
    'test_preflight.py' = '사전 점검이 API 키 값을 노출하지 않는지, 에이전트 포트를 안내성 정보로 처리하는지, 필수 점검 실패를 보고서에 표시하는지 검증'
    'test_retriever_search.py' = '범용어 과다 매칭 차단, 1차 0건 후 동의어 검색, 낮은 관련성 되살림 금지, 희소 구체어, 1글자 앱, 데이터 없음 주제, 상위 10건 제한을 검증'
}

$testGroups = @(
    $pytest.tests | Group-Object { ($_.nodeid -split '::')[0] } | ForEach-Object {
        $fileName = [IO.Path]::GetFileName($_.Name)
        [pscustomobject]@{
            File = $fileName
            Summary = $testSummary[$fileName]
            Count = $_.Count
            Passed = @($_.Group | Where-Object outcome -eq 'passed').Count
            Skipped = @($_.Group | Where-Object outcome -eq 'skipped').Count
            Seconds = [Math]::Round((($_.Group.duration_seconds | Measure-Object -Sum).Sum), 2)
        }
    } | Sort-Object File
)
$slowTests = @($pytest.tests | Sort-Object duration_seconds -Descending | Select-Object -First 6)

$responseTimes = @(
    foreach ($row in $scored) {
        $match = [regex]::Match($row.rationale, '응답시간[^0-9]*([0-9]+(?:\.[0-9]+)?)초')
        if ($match.Success) {
            [pscustomobject]@{ Case = $row.case_id; Seconds = [double]$match.Groups[1].Value }
        }
    }
)

$pytestChart = Join-Path $assets "pytest_결과분포.png"
$durationChart = Join-Path $assets "pytest_장시간테스트.png"
$verdictChart = Join-Path $assets "judge_판정분포.png"
$caseChart = Join-Path $assets "judge_케이스점수.png"
$metricChart = Join-Path $assets "judge_평가항목.png"
$responseChart = Join-Path $assets "judge_응답시간.png"

New-DonutChart -Path $pytestChart -Title "pytest 실행 결과" `
    -Labels @('PASS', 'SKIP') -Values @([double]$pytest.counts.passed, [double]$pytest.counts.skipped) `
    -Colors @('#2E8B57', '#8A94A6')
New-BarChart -Path $durationChart -Title "수행시간 상위 테스트" `
    -Labels @($slowTests | ForEach-Object { ($_.nodeid -split '::')[-1] }) `
    -Values @($slowTests | ForEach-Object { [double]$_.duration_seconds }) -Color '#5B6FB5' -ValueSuffix '초'
New-DonutChart -Path $verdictChart -Title "LLM Judge 판정 분포 (16개 채점 사례)" `
    -Labels $verdictShort -Values ([double[]]$verdictCounts) -Colors @('#2673B8', '#F0A43A', '#D95B59', '#8B1E2D')
New-BarChart -Path $caseChart -Title "케이스별 LLM Judge 총점" `
    -Labels @($scored.case_id) -Values @($scored | ForEach-Object { [double]$_.total }) `
    -Maximum 100 -Color '#2673B8' -ValueSuffix '점'
New-BarChart -Path $metricChart -Title "평가 항목별 평균 달성률" `
    -Labels @($metricStats.Name) -Values @($metricStats.Percent) -Maximum 100 -Color '#6A5ACD' -ValueSuffix '%'
if ($responseTimes.Count -gt 0) {
    New-BarChart -Path $responseChart -Title "로그에서 확인된 케이스별 응답시간" `
        -Labels @($responseTimes.Case) -Values @($responseTimes.Seconds) -Color '#C96B3B' -ValueSuffix '초'
}

$css = @"
<style>
@page { size: A4; margin: 18mm 18mm 18mm 18mm; }
body { font-family: '맑은 고딕'; color:#243247; font-size:10.2pt; line-height:1.55; }
.cover { text-align:center; padding-top:115px; min-height:760px; }
.cover .eyebrow { color:#2673B8; font-size:12pt; letter-spacing:2px; font-weight:bold; }
.cover h1 { color:#16243A; font-size:29pt; margin:28px 0 12px 0; line-height:1.25; }
.cover h2 { color:#5B6B82; font-size:15pt; font-weight:normal; margin:0 0 50px 0; }
.cover .rule { width:130px; height:5px; background:#2673B8; margin:26px auto; }
.cover .meta { margin:60px auto 0 auto; width:75%; border-top:1px solid #CBD5E1; padding-top:20px; color:#526176; }
h1 { color:#17375E; font-size:20pt; border-bottom:3px solid #2673B8; padding-bottom:8px; margin-top:26px; }
h2 { color:#244D75; font-size:14pt; border-left:6px solid #49A6A6; padding-left:10px; margin-top:24px; }
h3 { color:#315C83; font-size:11.5pt; margin-top:18px; }
p { margin:7px 0 10px 0; }
.lead { font-size:11pt; color:#354A63; background:#F2F6FA; border-left:5px solid #2673B8; padding:12px 15px; }
.note { background:#FFF8E8; border:1px solid #E9C86C; padding:10px 13px; color:#5E4B16; }
.danger { background:#FFF1F1; border-left:6px solid #B52B3A; padding:11px 14px; color:#70212B; }
.good { background:#EEF8F3; border-left:6px solid #2E8B57; padding:11px 14px; }
.pagebreak { page-break-before:always; }
table.data { border-collapse:collapse; width:100%; margin:10px 0 17px 0; font-size:9pt; }
table.data th { background:#244D75; color:white; padding:7px 6px; border:1px solid #D2DBE5; text-align:left; }
table.data td { padding:6px; border:1px solid #D2DBE5; vertical-align:top; }
table.data tr:nth-child(even) td { background:#F5F8FB; }
table.kpi { width:100%; border-collapse:separate; border-spacing:7px; margin:18px 0; }
table.kpi td { width:25%; background:#F2F6FA; border-top:5px solid #2673B8; text-align:center; padding:13px 5px; }
table.kpi.five td { width:20%; }
.knum { font-size:22pt; font-weight:bold; color:#17375E; }
.klabel { color:#627187; font-size:8.5pt; }
.figure { text-align:center; margin:16px 0 8px 0; }
.figure img { max-width:680px; }
.caption { text-align:center; color:#66758A; font-size:8.5pt; margin-bottom:16px; }
.toc { background:#F7F9FC; border:1px solid #D7E0EA; padding:18px 25px; }
.toc li { margin:7px 0; }
.small { font-size:8.5pt; color:#66758A; }
.conclusion { border:2px solid #244D75; padding:16px; background:#F8FAFC; }
</style>
"@

$generatedAt = Get-Date -Format "yyyy년 M월 d일 HH:mm"
$judgeDuration = ([datetimeoffset]$judge.finished_at - [datetimeoffset]$judge.started_at)
$judgeDurationText = "{0}분 {1}초" -f [int]$judgeDuration.TotalMinutes, $judgeDuration.Seconds
$pytestDurationText = "{0}분 {1}초" -f [int]([double]$pytest.duration_seconds / 60), [int]([double]$pytest.duration_seconds % 60)

$agentRows = @(
    @('Interpreter', '질문 의도·분석 범위·검색 필터 해석', 'OpenAI', '모호한 질문을 임의로 단정하지 않는지'),
    @('Retriever', 'CSV에서 관련 VOC 근거 검색', 'LLM 미사용', '관련성·과다/과소 검색'),
    @('Summarizer', '검색 근거의 핵심 불만과 영향 요약', 'OpenAI', '왜곡·누락·환각'),
    @('Evaluator', '요약 후보의 내부 품질 평가', 'OpenAI', '점수와 근거의 일관성'),
    @('Critic', '누락·과장·근거 부족·위험 탐지', 'OpenAI', '실제 결함을 놓치지 않는지'),
    @('Improver', '원인과 연결된 실행 가능한 개선안 작성', 'Anthropic', '담당·기한·검증 방법의 구체성'),
    @('독립 LLM Judge', '최종 산출물을 별도 관점으로 100점 평가', 'Anthropic 우선 / OpenAI 대체', '생성 단계와 분리된 객관성')
)

$testFileRows = @($testGroups | ForEach-Object { ,@($_.File, $_.Summary, $_.Count, $_.Passed, $_.Skipped, $_.Seconds) })
$slowRows = @($slowTests | ForEach-Object { ,@(($_.nodeid -split '::')[-1], $_.outcome, [Math]::Round([double]$_.duration_seconds, 2)) })
$metricRows = @($metricStats | ForEach-Object { ,@($_.Name, "$($_.Average) / $($_.Max)", "$($_.Percent)%") })
$caseRows = @($rows | ForEach-Object {
    $modelText = if ([string]::IsNullOrWhiteSpace($_.judge_model)) { '해당 없음' } else { $_.judge_model }
    $scoreText = if ([string]::IsNullOrWhiteSpace($_.total)) { '평균 제외' } else { $_.total }
    $attemptText = if ([string]::IsNullOrWhiteSpace($_.api_attempts)) { '해당 없음' } else { $_.api_attempts }
    ,@($_.case_id, $_.mode, $modelText, $scoreText, $_.verdict, $attemptText)
})
$topCases = @($scored | Sort-Object { [double]$_.total } -Descending | Select-Object -First 5)
$lowCases = @($scored | Sort-Object { [double]$_.total } | Select-Object -First 5)
$topRows = @($topCases | ForEach-Object { ,@($_.case_id, $_.total, $_.verdict, ($_.rationale.Substring(0, [Math]::Min(150, $_.rationale.Length)) + '…')) })
$lowRows = @($lowCases | ForEach-Object { ,@($_.case_id, $_.total, $_.verdict, ($_.rationale.Substring(0, [Math]::Min(170, $_.rationale.Length)) + '…')) })
$holdRows = @($immediate | ForEach-Object { ,@($_.case_id, $_.total, ($_.rationale.Substring(0, [Math]::Min(260, $_.rationale.Length)) + '…')) })
$evidenceRows = @(
    @('pytest JSON', '상태·건수·환경·테스트별 수행시간', $pytestLog),
    @('pytest LOG', '실행 순서와 상세 출력', (Join-Path $reports 'logs\pytest\pytest_20260715_142539_267083.log')),
    @('LLM Judge JSON', '실행 상태·모델·케이스별 판정·API 시도', $judgeLog),
    @('Judge CSV', '9개 항목 점수·총점·근거·실제 분석', $judgeCsv),
    @('점수 보고서', '평균·최종 판정·케이스 상세', $scoreMd),
    @('테스트 케이스', '질문·기대 결과·금지 출력·실행 구분', $casesJson)
)

$qaHtml = @"
<!doctype html><html><head><meta charset='utf-8'>$css</head><body>
<div class='cover'>
  <div class='eyebrow'>VOC IMPROVE · QUALITY ASSURANCE</div>
  <div class='rule'></div>
  <h1>VOC 개선 QA<br>점검완료보고서</h1>
  <h2>멀티 에이전트 구조 · 자동화 테스트 · 독립 품질진단</h2>
  <div class='meta'>
    작성 기준: $(ConvertTo-HtmlText $generatedAt)<br>
    실행 ID: $(ConvertTo-HtmlText $judge.run_id)<br>
    활용 범위: 수업 실습 · 팀 비교 · 발표 자료
  </div>
</div>

<div class='pagebreak'></div>
<h1>전체 결과 요약</h1>
<p class='lead'>이번 점검은 코드가 실행되는지만 확인하는 데 그치지 않고, 6개 에이전트의 연결 구조, 예외·분기·MCP·E2E 동작, 실행 로그의 추적성, 그리고 최종 VOC 분석 결과를 독립 Judge가 어떻게 평가했는지를 함께 확인했다.</p>
<table class='kpi'><tr>
<td><div class='knum'>$($pytest.counts.collected)</div><div class='klabel'>pytest 수집</div></td>
<td><div class='knum'>$($pytest.counts.passed)</div><div class='klabel'>pytest PASS</div></td>
<td><div class='knum'>$($judge.case_counts.processed)</div><div class='klabel'>Judge 처리</div></td>
<td><div class='knum'>$average</div><div class='klabel'>Judge 평균 / 100</div></td>
</tr></table>
<div class='danger'><b>종합 판단:</b> 자동화된 기능 점검은 75 PASS, 0 FAIL로 안정적이지만 VOC 결과 품질은 평균 $average점이고 즉시 보류 사례가 $($immediate.Count)건 확인되었다. 따라서 “실습 범위의 QA 실행 완료”와 “분석 결과의 배포 가능”을 구분해야 하며, 현재 상태는 <b>조건부 점검 완료·품질 개선 후 재검증 필요</b>로 판단한다.</div>

<h2>문서 구성</h2>
<div class='toc'><ol>
<li>프로젝트 목적과 점검 범위</li><li>멀티 에이전트 처리 구조</li><li>자동화 테스트 구성과 결과</li>
<li>독립 LLM Judge 수행 현황</li><li>장애 대응과 결함관리</li><li>잔여 위험과 개선 권고</li>
<li>증적관리</li><li>작성자 의견과 QA 결론</li></ol></div>

<div class='pagebreak'></div>
<h1>1. 프로젝트 목적과 점검 범위</h1>
<p>이 프로젝트는 강사가 제공한 예시 코드를 바탕으로, 수강자가 VOC 분석 과정을 개량하고 다른 팀의 결과와 비교하여 발표하기 위한 개발·시연용 프로젝트다. GUI는 서버·테스트·보고서 관리에 집중하고, 실제 대화형 VOC 분석은 Claude Desktop, VS Code, Antigravity 등 외부 MCP 클라이언트에서 이용하는 구조를 유지한다.</p>
<p>점검 범위는 질문 해석부터 VOC 검색, 요약, 내부 평가, 비판, 개선안 생성까지의 6개 에이전트 흐름과 MCP 진입점, 예외 처리, API 재시도, 독립 Judge, 실행 증적을 포함한다.</p>
<h2>점검 대상 구성</h2>
$(HtmlTable @('구성요소','주요 역할','API 사용','점검 초점') $agentRows)
<div class='note'><b>내부 평가와 독립 Judge의 차이:</b> Evaluator와 Critic은 생성 과정 안에서 결과를 보완하는 역할이고, 독립 Judge는 최종 산출물을 별도의 모델과 평가표로 다시 채점한다. 내부 단계의 자기평가 편향을 줄이고, 실패가 성공처럼 보이는지를 외부 관점에서 확인하기 위한 분리다.</div>

<h2>전체 처리 흐름</h2>
$(HtmlTable @('순서','처리 단계','산출물·통제') @(
@('1','사용자 질문 입력','질문 원문 및 분석 요청'),
@('2','Interpreter','의도·task·검색 필터'),
@('3','Retriever','관련 VOC 원문과 검색 건수'),
@('4','Summarizer','근거 기반 요약 후보'),
@('5','Evaluator','후보별 내부 평가'),
@('6','Critic','누락·과장·위험 지적'),
@('7','Improver','정책·절차 개선안'),
@('8','독립 LLM Judge','9개 항목 점수·판정·근거'),
@('9','로그·보고서','CSV·JSON·LOG·Markdown·DOCX 증적')
))

<div class='pagebreak'></div>
<h1>2. 자동화 테스트 구성과 결과</h1>
<p>pytest는 소스 구조, 구문, 에이전트 기본 동작, 예외 처리, 재시도, MCP 도구, 파이프라인 연결을 빠르게 반복 확인하는 내부 자동화 검사다. LLM Judge의 20개 VOC 시나리오와 중복되지 않도록 pytest에서는 장시간 자연어 케이스 반복을 제거하고 구조·분기·통합 검증에 집중했다.</p>
<table class='kpi'><tr>
<td><div class='knum'>$($pytest.counts.passed)</div><div class='klabel'>PASS</div></td>
<td><div class='knum'>$($pytest.counts.failed)</div><div class='klabel'>FAIL</div></td>
<td><div class='knum'>$($pytest.counts.errors)</div><div class='klabel'>ERROR</div></td>
<td><div class='knum'>$($pytest.counts.skipped)</div><div class='klabel'>SKIP</div></td>
</tr></table>
<div class='figure'><img src='$(FileUrl $pytestChart)'></div><div class='caption'>그림 1. pytest 결과 분포 — 76개 중 75개 통과, 1개 SKIP</div>
$(HtmlTable @('테스트 파일','한글 검증 요약','수집','PASS','SKIP','누적 수행시간(초)') $testFileRows)
<p class='small'>실행 환경: Python $(ConvertTo-HtmlText $pytest.python_version) / $(ConvertTo-HtmlText $pytest.platform), 총 수행시간 $pytestDurationText.</p>
<div class='note'><b>SKIP 1건 사유:</b> <code>test_analyze_voc_returns_error_dict_when_servers_down</code>는 Summarizer(6003) 서버가 실행 중이어서 “서버 다운” 조건을 재현할 수 없어 SKIP 처리됐다. 기능 미구현이나 테스트 실패가 아니며, 해당 장애 시나리오를 재현하려면 Summarizer 서버를 종료한 뒤 별도로 재실행해야 한다.</div>

<h2>장시간 테스트 분석</h2>
<div class='figure'><img src='$(FileUrl $durationChart)'></div><div class='caption'>그림 2. 수행시간 상위 테스트 — 실제 파이프라인과 MCP E2E 호출이 대부분의 시간을 차지</div>
$(HtmlTable @('테스트','상태','수행시간(초)') $slowRows)
<p>상위 6개 테스트가 전체 실행시간 대부분을 차지했다. 이 구간은 6개 에이전트와 외부 LLM 호출을 포함하므로 단위 테스트보다 느리다. 수업 시연에서는 빠른 정적·단위 점검과 실제 API 기반 E2E 점검을 버튼과 로그에서 명확히 구분하는 것이 적절하다.</p>

<div class='pagebreak'></div>
<h1>3. 독립 LLM Judge 수행 현황</h1>
<table class='kpi five'><tr>
<td><div class='knum'>$($judge.case_counts.total_defined)</div><div class='klabel'>정의된 케이스</div></td>
<td><div class='knum'>$($judge.case_counts.scored)</div><div class='klabel'>정식 채점</div></td>
<td><div class='knum'>$($noData.Count)</div><div class='klabel'>데이터 없음 PASS</div></td>
<td><div class='knum'>$($judge.case_counts.na)</div><div class='klabel'>API 실패 N/A</div></td>
<td><div class='knum'>2</div><div class='klabel'>pytest 전용 TC-19·20</div></td>
</tr></table>
<p>Judge는 $(ConvertTo-HtmlText $judge.started_at)부터 $(ConvertTo-HtmlText $judge.finished_at)까지 $judgeDurationText 동안 실행됐다. 20개 중 TC-01~16은 실제 분석 결과를 100점으로 채점했고, TC-17·18은 CSV에 없는 주제를 정확히 0건으로 판정해 <b>데이터 없음 PASS</b>로 평균에서 제외했다. TC-19는 Retriever 중단 시 명확한 오류 표시, TC-20은 CSV 누락 시 데이터 파일 오류 안내를 검증하는 <b>pytest 전용 장애 케이스</b>라 LLM 채점 대상에서 제외했다. 우선 Judge는 <b>anthropic:claude-sonnet-5</b>를 사용했으며, 16개 채점 사례는 모두 <b>anthropic:성공</b>으로 기록되어 API 재시도 실패에 따른 N/A는 없었다.</p>
<div class='figure'><img src='$(FileUrl $verdictChart)'></div><div class='caption'>그림 3. 정식 채점 16건의 판정 분포</div>
<div class='danger'>평균은 $average점이며 즉시 보류가 $($immediate.Count)건 발생했다. pytest 성공은 코드 구조와 정의된 동작의 안정성을 의미하지만, 생성된 분석 내용의 사실성·모호성 대응·위험 탐지까지 자동으로 보장하지는 않는다.</div>

<h2>API 장애 대응과 기록</h2>
$(HtmlTable @('항목','현재 설계','이번 실행 결과') @(
@('호출 실패','제공자별 최대 3회 시도','채점 API 실패 없음'),
@('3회 실패','0점이 아닌 N/A 처리','N/A 0건'),
@('평균 계산','N/A·데이터 없음 PASS·pytest 장애 케이스는 평균에서 제외','TC-01~16만 100점 채점 대상. TC-17·18은 0건 PASS, TC-19·20은 Retriever 중단·CSV 누락을 검증하는 pytest 전용이므로 16개만 평균 반영'),
@('보고서 표시','재시도 실패 원인과 제공자 기록','모든 채점 사례 anthropic:성공'),
@('대체 경로','Anthropic 우선, OpenAI 대체 가능','Anthropic이 3회 재시도 후에도 타임아웃·429·일시 장애로 실패하면 Judge 전체 중단을 피하고 채점을 계속하기 위해 OpenAI로 전환. 두 제공자가 모두 실패하면 N/A 처리. 이번은 대체 경로 미사용')
))

<div class='pagebreak'></div>
<h1>4. 장애 대응과 결함관리</h1>
<p>이번 실행에서 pytest 실패나 API N/A는 없었지만, 독립 Judge는 기능 테스트만으로 드러나지 않는 내용 품질 결함을 확인했다. 따라서 결함관리는 “테스트 실패”와 “최종 산출물 품질 저하”를 나누어 기록했다.</p>
$(HtmlTable @('구분','증상·근거','조치 상태','다음 검증') @(
@('검색 과다매칭','범용 지시어와 느슨한 단어 매칭으로 관련 없는 VOC가 다수 유입될 수 있었음','단계별 검색·범용어 제외·상위 10건 제한 적용, 전용 단위 테스트 통과','다음 Judge에서 Retriever count와 고객 ID 재확인'),
@('모호한 질문 단정','TC-08·13·14에서 추가 확인 없이 특정 문제로 좁혀 분석','미해결','Interpreter에 명시적 확인 질문 분기 추가'),
@('근거 이탈·환각','TC-15에서 Retriever 이후 요약이 검색 근거와 달라지고 후속 단계가 이를 충분히 차단하지 못함','미해결·고위험','고객 ID 기반 근거 검증과 파이프라인 중단 규칙 추가'),
@('복합 질문 누락','TC-16에서 본인 인증 문제를 누락하고 납입 내역만 개선','미해결','요구 항목 체크리스트와 Critic 누락 검사 강화'),
@('응답 지연','실제 API 기반 사례가 대체로 100초 이상 소요','미해결','입력 축약·호출 수 점검·데모용 빠른 경로 검토'),
@('데이터 대표성','Judge 의견에서 $($limitedCases.Count)개 사례가 표본 또는 대표성 한계를 언급','데이터 확장 필요','주제별 최소 표본과 다양한 표현을 보강한 뒤 재시험')
))

<h2>즉시 보류 사례</h2>
$(HtmlTable @('케이스','점수','핵심 근거') $holdRows)
<p>즉시 보류는 점수의 높고 낮음과 별개로 다뤘다. 모호한 질문을 근거 없이 확정하거나, 검색 근거와 다른 내용을 만든 뒤 성공한 것처럼 파이프라인이 계속 진행하는 경우에는 기능 테스트가 통과했더라도 배포 판단을 중단해야 한다.</p>

<h2>잔여 위험과 권고</h2>
$(HtmlTable @('위험','영향','가능성','우선 조치') @(
@('모호한 질문의 임의 해석','잘못된 VOC·정책으로 연결','높음','추가 질문 또는 분석 보류 분기'),
@('요약의 검색 근거 이탈','환각과 잘못된 개선안 생성','중간~높음','Retriever ID와 요약 인용의 자동 대조'),
@('VOC 표본 부족','비교·일반화의 신뢰도 저하','높음','주제별 데이터 확장과 최소 표본 기준'),
@('외부 API 지연·비용','시연 시간 증가와 중단 가능성','중간','캐시·요청 축약·빠른 데모 시나리오'),
@('단일 Judge 의존','평가 변동 가능성','중간','동일 로그 재채점과 결과 비교')
))

<div class='pagebreak'></div>
<h1>5. 산출물과 실행 증적</h1>
$(HtmlTable @('자료','활용 목적','저장 위치') $evidenceRows)
<p class='small'>API 키와 민감한 환경변수 값은 문서에 포함하지 않았다. 원본 JSON과 CSV는 표·그래프 수치의 추적 근거로 사용하며, DOCX에는 발표와 검토에 필요한 요약만 담았다.</p>

<h1>6. 작성자 의견과 QA 완료 결론</h1>
<div class='conclusion'>
<p><b>작성자 의견.</b> 자동화 테스트 결과만 보면 구조·문법·예외·분기·MCP·E2E 흐름은 안정적으로 준비되어 있다. 76개 중 75개가 통과했고 실패와 오류가 없으며, 실행 로그도 JSON·LOG·CSV·Markdown으로 추적 가능하다. 이 점은 수업 실습과 팀 비교 발표에서 프로젝트의 구현 과정과 검증 근거를 설명하기에 충분한 장점이다.</p>
<p>다만 독립 Judge 결과는 기능의 정상 동작과 답변의 신뢰성이 같은 의미가 아님을 보여 준다. 평균 $average점, 즉시 보류 $($immediate.Count)건, Critic 위험 탐지 달성률 저하, 100초 전후의 응답시간은 다음 개선이 필요하다는 신호다. 특히 현재 VOC 데이터가 50건 규모이고 여러 평가 사례에서 관련 표본이 1~2건에 그쳐 점수에 일정 부분 영향을 준 것으로 판단된다. 그러나 데이터 부족만으로 TC-15의 근거 이탈이나 TC-13·14의 모호성 단정까지 설명할 수는 없다. 데이터 확장과 함께 에이전트의 중단·확인·근거 대조 로직을 동시에 보완해야 한다.</p>
<p><b>최종 결론.</b> 본 실행은 <b>실습 범위의 QA 점검은 완료</b>되었으나, 실제 VOC 분석 품질은 <b>조건부 완료·개선 후 재검증 필요</b>로 판정한다. 우선순위는 ① 모호한 질문 확인 분기, ② 검색 근거와 요약의 고객 ID 대조, ③ Critic의 누락·환각 탐지 강화, ④ 주제별 VOC 표본 확장, ⑤ 응답시간 단축 순이다.</p>
</div>
</body></html>
"@

$qualityHtml = @"
<!doctype html><html><head><meta charset='utf-8'>$css</head><body>
<div class='cover'>
  <div class='eyebrow'>VOC ANALYSIS · INDEPENDENT QUALITY REVIEW</div>
  <div class='rule' style='background:#6A5ACD'></div>
  <h1>VOC 분석<br>종합품질평가보고서</h1>
  <h2>20개 테스트 케이스 · 9개 평가 항목 · 독립 LLM Judge</h2>
  <div class='meta'>
    평가 기준일: $(ConvertTo-HtmlText $generatedAt)<br>
    Judge 모델: anthropic:claude-sonnet-5<br>
    활용 범위: 수업 실습 · 팀 비교 · 발표 자료
  </div>
</div>

<div class='pagebreak'></div>
<h1>품질 대시보드</h1>
<table class='kpi five'><tr>
<td><div class='knum'>$average</div><div class='klabel'>평균 점수</div></td>
<td><div class='knum'>$($scored.Count)</div><div class='klabel'>정식 채점</div></td>
<td><div class='knum'>$($immediate.Count)</div><div class='klabel'>즉시 보류</div></td>
<td><div class='knum'>$($judge.case_counts.na)</div><div class='klabel'>API 실패 N/A</div></td>
<td><div class='knum'>2</div><div class='klabel'>pytest 전용 TC-19·20</div></td>
</tr></table>
<div class='note'><b>TC-19·20 분리 이유:</b> TC-19는 Retriever 중단 시 명확한 오류 표시, TC-20은 CSV 누락 시 데이터 파일 오류 안내를 검증한다. 이 두 케이스는 생성 답변의 품질을 점수로 판단하는 시나리오가 아니라, 장애 조건에서 정해진 오류 처리가 실행되는지를 결정적으로 확인하는 테스트이므로 LLM Judge 변동성·API 비용의 영향을 받지 않도록 pytest 전용으로 분리했다.</div>
<div class='danger'><b>최종 품질 판정: 배포 보류.</b> 평균이 69점 이하이고, 별도로 즉시 보류 사례가 2건 확인되었다. 기능 테스트 성공과 별개로 모호성 대응, 검색 근거 유지, Critic 위험 탐지, 성능을 개선한 뒤 동일 케이스로 재검증해야 한다.</div>
<div class='figure'><img src='$(FileUrl $verdictChart)'></div><div class='caption'>그림 1. LLM Judge 판정 분포</div>

<h2>문서 구성</h2>
<div class='toc'><ol><li>평가 대상과 방법</li><li>케이스별 점수와 판정</li><li>9개 평가 항목 분석</li>
<li>에이전트별 강점과 약점</li><li>우수·취약 사례</li><li>즉시 보류와 데이터 한계</li>
<li>성능·API 분석</li><li>개선 우선순위</li><li>작성자 의견과 최종 결론</li></ol></div>

<div class='pagebreak'></div>
<h1>1. 평가 대상과 방법</h1>
<p>20개 테스트 케이스 중 실제 LLM Judge 대상은 18개다. TC-01~16은 100점 기준으로 정식 채점했고, TC-17·18은 현재 CSV에 존재하지 않는 주제를 정확히 0건으로 판정하는지가 정답이므로 PASS(예외처리)로 평균에서 제외했다. TC-19·20은 Retriever 중단과 CSV 누락을 검증하는 pytest 전용 장애 사례다.</p>
<p>최종 결과를 생성한 내부 Evaluator·Critic과 독립 Judge를 분리하여, 생성 단계가 자신의 출력을 관대하게 평가하는 문제를 줄였다. Judge는 각 사례의 질문, 기대 의도, 필수 출력, 금지 출력, 실제 파이프라인 결과를 함께 검토했다.</p>
$(HtmlTable @('평가 항목','배점','평가 초점') @(
@('Interpreter 해석 정확성','15','질문 의도와 검색 조건'),
@('Retriever 검색 관련성','15','관련 VOC 근거와 대표성'),
@('Summarizer 사실성·요약성','15','왜곡·누락 없는 핵심 요약'),
@('Evaluator 평가 타당성','10','점수와 근거의 일관성'),
@('Critic 위험 탐지력','10','환각·누락·과장·근거 부족 탐지'),
@('Improver 실행 가능성','15','원인과 연결된 구체적 실행안'),
@('Agent 연계 품질','10','앞 단계 결과의 정확한 전달'),
@('장애 대응·로그','5','오류 표시와 추적 가능성'),
@('성능','5','수업 시연에서 허용 가능한 응답시간')
))

<div class='pagebreak'></div>
<h1>2. 케이스별 점수와 판정</h1>
<div class='figure'><img src='$(FileUrl $caseChart)'></div><div class='caption'>그림 2. TC-01~16 총점 — 평균 $average점</div>
$(HtmlTable @('케이스','실행 유형','Judge 모델','총점','판정','API 시도') $caseRows)
<p class='note'>TC-17·18의 0건은 실패가 아니라 설계된 정답이다. 반대로 TC-08과 TC-15는 점수와 별개로 근거 없는 단정 또는 검색 근거 이탈이 확인되어 즉시 보류됐다.</p>

<h2>점수 분포 해석</h2>
<p>80점 이상 조건부 배포 가능 사례는 6건, 70점대 주요 개선 필요 사례는 3건, 69점 이하 배포 보류는 5건, 즉시 보류는 2건이었다. 우수 사례와 취약 사례의 차이는 단순히 Retriever 검색 건수보다, 모호한 질문을 안전하게 처리했는지와 검색된 고객 불만이 Summarizer·Evaluator·Critic·Improver까지 유지됐는지에서 크게 발생했다.</p>

<div class='pagebreak'></div>
<h1>3. 9개 평가 항목 분석</h1>
<div class='figure'><img src='$(FileUrl $metricChart)'></div><div class='caption'>그림 3. 항목별 배점 대비 평균 달성률</div>
$(HtmlTable @('평가 항목','평균 / 배점','달성률') $metricRows)
<h2>상대적 강점</h2>
<p><b>장애 대응·로그</b>는 77.5%로 가장 높았고, Interpreter와 Retriever도 각각 약 75.8%, 74.2% 수준이었다. 단계별 결과와 API 성공 여부가 남아 있어 저점 사례에서도 원인을 추적할 수 있었다. 질문이 구체적인 TC-01·04·06·10·12에서는 Interpreter가 핵심 요소를 필터에 잘 반영했고 Retriever도 직접 관련된 VOC를 찾았다.</p>
<h2>우선 개선 영역</h2>
<p><b>Critic 위험 탐지력</b>은 45.6%로 가장 낮았다. 데이터가 적거나 질문이 모호한데도 need_refine=false로 진행하거나, 복합 질문의 일부 누락과 근거 이탈을 충분히 차단하지 못했다. <b>성능</b>도 52.5%에 그쳐 수업 시연에서 체감 지연이 큰 상태다. Summarizer·Evaluator·Improver는 형식적으로 완성된 출력을 만들었지만, 잘못된 전제가 들어오면 그 전제를 강화하는 방향으로 연계되는 문제가 반복됐다.</p>

<h2>에이전트별 관찰</h2>
$(HtmlTable @('단계','확인된 강점','반복된 약점') @(
@('Interpreter','구체적 복합 질문의 핵심 요소를 필터로 반영','모호한 질문에서 확인 질문 없이 임의의 원인으로 좁힘'),
@('Retriever','구체 질문에서는 직접 관련 VOC 검색','표본 1~2건과 모호 질문의 잘못된 검색에 취약'),
@('Summarizer','근거가 적절할 때 사실 중심 요약','TC-15 근거 이탈, TC-16 복합 이슈 일부 누락'),
@('Evaluator','후보 품질을 구조화해 평가','잘못된 요약을 전제로 높은 점수를 줄 수 있음'),
@('Critic','일부 사례에서 과장·근거 부족을 구체적으로 지적','모호성·표본 부족·반쪽 분석을 놓친 사례가 많음'),
@('Improver','담당·기한·실행 방법을 포함한 구체적 안 제시','잘못된 전제 위에서도 실행 가능한 듯한 정책을 생성'),
@('Agent 연계','정상 사례에서는 자연스러운 단계 연결','오류 발생 시 다음 단계가 오류를 증폭시키는 구조')
))

<div class='pagebreak'></div>
<h1>4. 우수 사례와 취약 사례</h1>
<h2>상위 5개 사례</h2>
$(HtmlTable @('케이스','점수','판정','Judge 핵심 의견') $topRows)
<p>상위 사례는 질문에 포함된 핵심 요소가 필터에 명확히 반영되고, 검색된 VOC가 요약과 개선안까지 유지되었다. 특히 TC-10과 TC-12는 담당 부서, 기한, 실행 방법이 포함된 개선안으로 높은 평가를 받았다. 다만 상위 사례도 표본 수와 응답시간 한계는 남아 있다.</p>

<h2>하위 5개 사례</h2>
$(HtmlTable @('케이스','점수','판정','Judge 핵심 의견') $lowRows)
<p>하위 사례는 “질문이 모호함 → Interpreter가 임의로 구체화 → Retriever가 특정 사례를 선택 → 이후 단계가 잘못된 전제를 강화”하는 흐름이 반복됐다. 단순히 문장을 더 그럴듯하게 만드는 것으로 해결되지 않으며, 분석을 잠시 멈추고 사용자에게 추가 정보를 요청하는 분기가 필요하다.</p>

<div class='pagebreak'></div>
<h1>5. 즉시 보류와 데이터 한계</h1>
<h2>즉시 보류 사례</h2>
$(HtmlTable @('케이스','점수','발생 내용') $holdRows)
<div class='danger'>TC-08은 정보가 부족한 질문을 확정적으로 좁혀 정책까지 제시했고, TC-15는 검색 결과와 무관한 요약 및 근거 불명확한 인용이 후속 단계로 전달됐다. 이러한 유형은 평균 점수와 무관하게 배포를 중단해야 한다.</div>

<h2>VOC 데이터 규모가 평가에 미친 영향</h2>
<p>현재 `voc.csv`는 50건 규모이며, Judge 의견에서 $($limitedCases.Count)개 사례가 표본 수 또는 대표성 부족을 직접 언급했다. TC-01·02·06·10·11 등은 질문과 직접 관련된 사례를 찾았지만 대부분 1~2건에 머물러 공통 원인과 개선 우선순위를 일반화하기 어려웠다. 이 점은 Retriever, Summarizer, Critic, Agent 연계 점수에 실제 영향을 준 것으로 판단된다.</p>
<p class='note'>그러나 낮은 점수를 모두 데이터 부족으로 해석해서는 안 된다. TC-13·14의 모호성 단정, TC-15의 근거 이탈, TC-16의 복합 이슈 누락은 데이터 양과 별도로 처리 로직을 개선해야 하는 문제다. 다음 재시험에서는 데이터 확장과 에이전트 안전장치를 함께 적용해야 원인을 분리해 비교할 수 있다.</p>

<div class='pagebreak'></div>
<h1>6. 성능과 API 안정성</h1>
$(if ($responseTimes.Count -gt 0) { "<div class='figure'><img src='$(FileUrl $responseChart)'></div><div class='caption'>그림 4. Judge 근거에서 응답시간이 명시된 사례</div>" })
<p>응답시간이 명시된 사례 대부분이 약 96~126초 범위였으며, 단순하거나 모호한 문의도 100초 이상 소요됐다. 6개 에이전트가 순차적으로 외부 LLM을 호출하는 구조가 정확성 검증에는 도움이 되지만 시연 흐름에는 부담이 된다.</p>
$(HtmlTable @('항목','결과','해석') @(
@('Judge 우선 모델','anthropic:claude-sonnet-5','생성 모델과 분리된 독립 평가'),
@('대체 모델','openai:gpt-5.4-mini 구성','Anthropic 실패 시 대체 가능'),
@('API 성공','채점 16건 모두 anthropic:성공','이번 실행에서 재시도 실패 없음'),
@('N/A','0건','평균에서 제외할 API 장애 사례 없음'),
@('Judge 총 실행시간',$judgeDurationText,'18개 사례 순차 처리로 장시간 소요')
))

<h2>성능 개선 방향</h2>
<ul><li>검색 결과와 프롬프트 입력을 필요한 근거만 남기도록 축약한다.</li><li>모호한 질문은 6개 에이전트를 모두 실행하기 전에 확인 질문으로 종료한다.</li><li>반복되는 평가 프롬프트와 안전한 정적 결과를 캐시할 수 있는지 검토한다.</li><li>수업 시연은 대표 사례 2~3건을 사용하고 전체 18건은 사전 실행 로그로 제시한다.</li></ul>

<div class='pagebreak'></div>
<h1>7. 개선 우선순위</h1>
$(HtmlTable @('우선순위','대상','구체 조치','재검증 방법') @(
@('1','Interpreter·MCP','모호성 점수를 계산하고 정보 부족 시 확인 질문 또는 분석 보류','TC-08·13·14에서 특정 원인 단정이 사라지는지 확인'),
@('2','Summarizer·Critic','검색 고객 ID와 요약 근거를 대조하고 불일치 시 파이프라인 실패 처리','TC-15에서 검색 외 내용 생성 시 즉시 중단'),
@('3','Critic·Agent 연계','required_output 체크리스트와 복합 이슈 누락 검사를 추가','TC-16 두 이슈가 요약·정책에 모두 남는지 확인'),
@('4','VOC 데이터','주제별 최소 3~5건, 표현·채널·심각도 변형을 포함해 확장','표본 확대 전후 Retriever·Critic 점수 비교'),
@('5','성능','프롬프트 축약, 불필요 호출 제거, 데모용 빠른 경로 분리','대표 사례의 95백분위 응답시간 비교')
))

<h1>8. 작성자 의견과 최종 품질 결론</h1>
<div class='conclusion'>
<p><b>작성자 의견.</b> 이번 결과에서 가장 긍정적인 점은 문제가 발생한 위치를 추적할 수 있다는 것이다. 9개 항목 점수, Judge 근거, 실제 분석 내용, API 성공 여부가 함께 남아 있어 단순한 성공률보다 훨씬 구체적으로 개선 방향을 설명할 수 있다. 구체적 질문에서는 Interpreter와 Retriever가 안정적으로 동작했고, Improver도 담당·기한·검증 방법이 있는 실행안을 제시했다.</p>
<p>반면 평균 $average점과 즉시 보류 2건은 현재 결과를 배포 가능한 수준으로 설명하기 어렵게 한다. 특히 Critic이 데이터 부족, 모호성, 근거 이탈을 놓친 사례가 반복되었다. 현재 VOC 데이터가 충분히 다양하지 않아 여러 사례의 점수가 낮아진 측면은 분명하다. 관련 VOC가 1~2건이면 요약의 사실성은 유지할 수 있어도 공통 원인과 우선순위를 일반화하기 어렵다. 다만 데이터가 늘어나는 것만으로 잘못된 전제의 확정과 환각이 자동으로 해결되지는 않는다.</p>
<p><b>최종 결론.</b> 현재 프로젝트는 수업 실습과 발표에서 멀티 에이전트 구조, 내부 검증, 독립 Judge, 로그 기반 결함 분석을 보여 주기에는 충분하다. 그러나 최종 VOC 분석 품질은 <b>배포 보류</b>이며, 모호성 확인 분기와 근거 대조를 먼저 고친 뒤 데이터를 확장하고 동일 18개 사례를 재실행해야 한다. 재시험에서는 평균 점수뿐 아니라 즉시 보류 0건, Critic 탐지력 개선, 복합 질문 누락 제거, 응답시간 감소를 함께 확인하는 것이 타당하다.</p>
</div>

<div class='pagebreak'></div>
<h1>부록. 케이스별 평가 근거 위치</h1>
<p>아래 원본 자료를 통해 본문의 모든 점수와 판단을 다시 확인할 수 있다.</p>
$(HtmlTable @('자료','활용 목적','저장 위치') $evidenceRows)
<p class='small'>본 보고서는 예시 문서의 내용 범위만 참고하고 현재 실행 로그의 수치와 사례만 사용해 새롭게 구성했다.</p>
</body></html>
"@

function Convert-HtmlToDocx {
    param(
        [string]$Html,
        [string]$TempHtml,
        [string]$DocxPath,
        [string]$HeaderText
    )
    [IO.File]::WriteAllText($TempHtml, $Html, [Text.UTF8Encoding]::new($true))
    $word = $null
    $doc = $null
    try {
        $word = New-Object -ComObject Word.Application
        $word.Visible = $false
        $word.DisplayAlerts = 0
        $doc = $word.Documents.Open($TempHtml)
        foreach ($section in $doc.Sections) {
            $section.PageSetup.TopMargin = $word.CentimetersToPoints(1.8)
            $section.PageSetup.BottomMargin = $word.CentimetersToPoints(1.8)
            $section.PageSetup.LeftMargin = $word.CentimetersToPoints(1.8)
            $section.PageSetup.RightMargin = $word.CentimetersToPoints(1.8)
            $header = $section.Headers.Item(1).Range
            $header.Text = $HeaderText
            $header.Font.Name = "맑은 고딕"
            $header.Font.Size = 8
            $header.Font.Color = 8421504
            $footer = $section.Footers.Item(1)
            $footer.Range.Font.Name = "맑은 고딕"
            $footer.Range.Font.Size = 8
            $footer.PageNumbers.Add() | Out-Null
        }
        foreach ($table in $doc.Tables) {
            $table.Rows.AllowBreakAcrossPages = $false
            $table.Range.Font.Name = "맑은 고딕"
        }
        # HTML에서 불러온 차트를 외부 링크로 남기지 않고 DOCX 내부에 포함한다.
        foreach ($shape in $doc.InlineShapes) {
            try {
                $shape.LinkFormat.SavePictureWithDocument = $true
                $shape.LinkFormat.BreakLink()
            }
            catch {
                # 링크가 아닌 InlineShape은 이미 문서에 포함된 상태이므로 계속 진행한다.
            }
        }
        $doc.SaveAs2($DocxPath, 16)
    }
    finally {
        if ($doc -ne $null) { $doc.Close($false) }
        if ($word -ne $null) { $word.Quit() }
        if (Test-Path -LiteralPath $TempHtml) { [IO.File]::Delete($TempHtml) }
        [GC]::Collect()
        [GC]::WaitForPendingFinalizers()
    }
}

$qaDocx = Join-Path $reports "VOC_개선_QA_점검완료보고서.docx"
$qualityDocx = Join-Path $reports "VOC_분석_종합품질평가보고서.docx"
Convert-HtmlToDocx -Html $qaHtml -TempHtml (Join-Path $assets "qa_report_temp.html") `
    -DocxPath $qaDocx -HeaderText "VOC 개선 QA 점검완료보고서  |  수업 실습·발표용"
Convert-HtmlToDocx -Html $qualityHtml -TempHtml (Join-Path $assets "quality_report_temp.html") `
    -DocxPath $qualityDocx -HeaderText "VOC 분석 종합품질평가보고서  |  독립 LLM Judge"

Write-Output $qaDocx
Write-Output $qualityDocx
