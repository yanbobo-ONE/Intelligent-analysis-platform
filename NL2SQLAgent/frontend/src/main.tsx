import React, { useEffect, useMemo, useRef, useState } from 'react';
import ReactDOM from 'react-dom/client';
import * as echarts from 'echarts';

type SessionItem = {
  id: string;
  title: string;
  created_at?: string;
  updated_at?: string;
  status: 'active' | 'idle';
};

type MessageItem = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at?: string;
};

type BackendSession = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
};

type BackendMessage = {
  id: string;
  session_id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
};

type ChatResponse = {
  answer_text: string;
  table_data: Array<[string, number]>;
  chart_spec: {
    type: string;
    xField: string;
    yField: string;
    seriesField?: string;
  };
  trace: {
    model: string;
    latency_ms: number;
    sql: string;
    tool_calls: unknown[];
    streaming: boolean;
  };
};

type ModelOption = {
  id: string;
  label: string;
};

const MODEL_OPTIONS: ModelOption[] = [
  { id: 'qwen3-max', label: 'qwen3-max' },
  { id: 'gpt-5.3-codex', label: 'gpt-5.3-codex' },
  { id: 'Kimi For Coding', label: 'Kimi For Coding' },
  { id: 'mimo-v2-omni-claude', label: 'mimo-v2-omni-claude' },
  { id: 'mimo-v2-pro-claude', label: 'mimo-v2-pro-claude' },
  { id: 'mimo-v2-tts-claude', label: 'mimo-v2-tts-claude' },
  { id: 'MiniMax M2.7', label: 'MiniMax M2.7' },
  { id: 'mimo-v2-omni-oai', label: 'mimo-v2-omni-oai' },
  { id: 'mimo-v2-pro-oai', label: 'mimo-v2-pro-oai' },
  { id: 'mimo-v2-tts-oai', label: 'mimo-v2-tts-oai' },
];

const API_BASE_URL = 'http://127.0.0.1:8000';
const DEFAULT_VENDOR_BASE_URL = 'https://cpa.ceastar.cn/v1';

function maskSecret(value: string) {
  if (!value) return '';
  return '******';
}

type ChartMode = 'bar' | 'line' | 'table';

function ChartPanel({ tableData }: { tableData: Array<[string, number]> }) {
  const chartRef = useRef<HTMLDivElement | null>(null);
  const chartInstanceRef = useRef<echarts.ECharts | null>(null);
  const [chartMode, setChartMode] = useState<ChartMode>('bar');

  useEffect(() => {
    if (!chartRef.current) return;
    if (tableData.length === 0) {
      if (chartInstanceRef.current) {
        chartInstanceRef.current.dispose();
        chartInstanceRef.current = null;
      }
      return;
    }

    if (chartMode === 'table') {
      return;
    }

    const chart = chartInstanceRef.current ?? echarts.init(chartRef.current);
    chartInstanceRef.current = chart;
    const chartType = chartMode === 'line' ? 'line' : 'bar';
    const categories = tableData.map(([name]) => String(name));
    const values = tableData.map(([, value]) => Number(value));
    chart.setOption({
      title: { text: 'NL2SQL 图表', left: 'center' },
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: categories, axisLabel: { interval: 0 } },
      yAxis: { type: 'value' },
      series: [{ data: values, type: chartType, smooth: chartMode === 'line' }],
    }, true);
    chart.resize();

    const handleResize = () => chart.resize();
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, [tableData, chartMode]);

  const renderContent = () => {
    if (tableData.length === 0) {
      return <div style={styles.emptyState}>暂无查询结果，请重新输入分析问题</div>;
    }

    return (
      <div style={styles.chartContentWrap}>
        <div style={{ ...styles.chart, display: chartMode === 'table' ? 'none' : 'block' }} ref={chartRef} />
        {chartMode === 'table' ? (
          <div style={styles.dataTable}>
            <div style={styles.dataTableHeader}>
              <span>维度</span>
              <span>数值</span>
            </div>
            {tableData.map(([name, value]) => (
              <div key={name} style={styles.dataTableRow}>
                <span>{name}</span>
                <span>{value}</span>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    );
  };

  return (
    <div>
      <div style={styles.chartToolbar}>
        <button style={chartMode === 'bar' ? styles.chartButtonActive : styles.chartButton} onClick={() => setChartMode('bar')}>柱状图</button>
        <button style={chartMode === 'line' ? styles.chartButtonActive : styles.chartButton} onClick={() => setChartMode('line')}>折线图</button>
        <button style={chartMode === 'table' ? styles.chartButtonActive : styles.chartButton} onClick={() => setChartMode('table')}>表格</button>
      </div>
      {renderContent()}
    </div>
  );
}

function App() {
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [draft, setDraft] = useState('');
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState('');
  const [tableData, setTableData] = useState<Array<[string, number]>>([]);
  const [generatedSql, setGeneratedSql] = useState('');
  const [analysisResult, setAnalysisResult] = useState<ChatResponse | null>(null);
  const [selectedModel, setSelectedModel] = useState('gpt-5.3-codex');
  const [vendorBaseUrl, setVendorBaseUrl] = useState(DEFAULT_VENDOR_BASE_URL);
  const [vendorApiKey, setVendorApiKey] = useState('');
  const [vendorApiKeyPlain, setVendorApiKeyPlain] = useState('');
  const [viewportWidth, setViewportWidth] = useState(window.innerWidth);
  const [inlineError, setInlineError] = useState('');
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [isCreatingSession, setIsCreatingSession] = useState(false);

  const activeSession = useMemo(() => sessions.find((session) => session.id === activeSessionId) ?? sessions.find((session) => session.status === 'active'), [sessions, activeSessionId]);
  const isMobile = viewportWidth < 1200;

  const loadSessions = async () => {
    const response = await fetch(`${API_BASE_URL}/api/sessions`);
    const data: BackendSession[] = await response.json();
    const normalized: SessionItem[] = data.map((s, idx) => ({
      ...s,
      status: idx === 0 ? 'active' : 'idle',
    }));
    setSessions(normalized);
    if (!activeSessionId && normalized.length > 0) {
      setActiveSessionId(normalized[0].id);
    }
  };

  const loadMessages = async (sessionId: string) => {
    const response = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}/messages`);
    const data: BackendMessage[] = await response.json();
    setMessages(
      data.map((m) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        created_at: m.created_at,
      })),
    );
  };

  useEffect(() => {
    const handleResize = () => setViewportWidth(window.innerWidth);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  useEffect(() => {
    const storedModel = localStorage.getItem('smart_analysis_model');
    const storedBaseUrl = localStorage.getItem('smart_analysis_vendor_base_url');
    const storedApiKey = localStorage.getItem('smart_analysis_vendor_api_key');
    if (storedModel) setSelectedModel(storedModel);
    if (storedBaseUrl) setVendorBaseUrl(storedBaseUrl);
    if (storedApiKey) {
      setVendorApiKey(storedApiKey);
      setVendorApiKeyPlain(storedApiKey);
    }
  }, []);

  useEffect(() => {
    localStorage.setItem('smart_analysis_model', selectedModel);
  }, [selectedModel]);

  useEffect(() => {
    localStorage.setItem('smart_analysis_vendor_base_url', vendorBaseUrl);
  }, [vendorBaseUrl]);

  useEffect(() => {
    localStorage.setItem('smart_analysis_vendor_api_key', vendorApiKeyPlain);
    setVendorApiKey(vendorApiKeyPlain ? maskSecret(vendorApiKeyPlain) : '');
  }, [vendorApiKeyPlain]);

  useEffect(() => {
    loadSessions().catch(() => {
      setSessions([{ id: 'fallback', title: '默认会话', status: 'active' }]);
      setActiveSessionId('fallback');
      setMessages([{ id: 'm-fallback', role: 'assistant', content: '后端不可用，当前为本地占位模式。' }]);
    });
  }, []);

  useEffect(() => {
    if (!activeSession) return;
    loadMessages(activeSession.id).catch(() => {
      setMessages([]);
      setGeneratedSql('');
      setTableData([]);
    });
  }, [activeSession?.id]);

  useEffect(() => {
    if (analysisResult?.table_data) {
      setTableData(analysisResult.table_data);
    }
    if (analysisResult?.trace?.sql) {
      setGeneratedSql(analysisResult.trace.sql);
    }
  }, [analysisResult]);

  const setActiveSession = (id: string) => {
    setActiveSessionId(id);
    setMessages([]);
    setGeneratedSql('');
    setTableData([]);
    setAnalysisResult(null);
    setSessions((prev) => prev.map((session) => ({ ...session, status: session.id === id ? 'active' : 'idle' })));
  };

  const addSession = async () => {
    if (isCreatingSession) return;
    setIsCreatingSession(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: '新建会话' }),
      });
      const created: BackendSession = await response.json();
      setActiveSessionId(created.id);
      setSessions((prev) => {
        const filtered = prev.filter((session) => session.id !== created.id);
        return [{ ...created, status: 'active' }, ...filtered.map((s) => ({ ...s, status: 'idle' }))];
      });
      setMessages([]);
      setGeneratedSql('');
      setTableData([]);
      setAnalysisResult(null);
      await loadMessages(created.id).catch(() => {
        setMessages([]);
      });
    } finally {
      setIsCreatingSession(false);
    }
  };

  const startEdit = (session: SessionItem) => {
    setEditingSessionId(session.id);
    setEditingTitle(session.title);
  };

  const confirmEdit = async () => {
    if (!editingSessionId || !editingTitle.trim()) return;
    await fetch(`${API_BASE_URL}/api/sessions/${editingSessionId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: editingTitle.trim() }),
    });
    setSessions((prev) => prev.map((s) => (s.id === editingSessionId ? { ...s, title: editingTitle.trim() } : s)));
    setEditingSessionId(null);
    setEditingTitle('');
  };

  const removeSession = async (id: string) => {
    await fetch(`${API_BASE_URL}/api/sessions/${id}`, { method: 'DELETE' });
    const next = sessions.filter((s) => s.id !== id);
    if (next.length > 0 && !next.some((s) => s.status === 'active')) {
      next[0].status = 'active';
      setActiveSessionId(next[0].id);
    } else if (next.length === 0) {
      setActiveSessionId(null);
      setMessages([]);
      setGeneratedSql('');
      setTableData([]);
      setAnalysisResult(null);
    }
    setSessions(next);
  };

  const sendChat = async (sessionId: string, message: string) => {
    const response = await fetch(`${API_BASE_URL}/api/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Model-Name': selectedModel,
        'X-Base-Url': vendorBaseUrl,
      },
      body: JSON.stringify({
        sessionId,
        message,
        model: selectedModel,
        baseUrl: vendorBaseUrl,
        apiKey: vendorApiKeyPlain,
      }),
    });
    const body = await response.json().catch(() => null);
    if (!response.ok) {
      throw new Error(body?.detail || `HTTP ${response.status}`);
    }
    return body as ChatResponse;
  };

  const sendMessage = async () => {
    if (!draft.trim() || !activeSession) return;
    if ((selectedModel || vendorBaseUrl) && !vendorApiKeyPlain.trim()) {
      setInlineError('请先填写 API Key');
      return;
    }

    setInlineError('');
    const userMessage: MessageItem = { id: `m${Date.now()}`, role: 'user', content: draft.trim() };
    const streamPlaceholder: MessageItem = { id: '__stream__', role: 'assistant', content: '生成中...' };
    setMessages((prev) => [...prev, userMessage, streamPlaceholder]);
    const userText = draft.trim();
    setDraft('');

    try {
      const result = await sendChat(activeSession.id, userText);
      setAnalysisResult(result);
      setMessages((prev) => prev.map((msg) => (msg.id === '__stream__' ? { ...msg, content: result.answer_text || '暂无结果' } : msg)));
      setGeneratedSql(result.trace?.sql || '');
      setTableData(result.table_data || []);
      await loadMessages(activeSession.id);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      setMessages((prev) => prev.map((msg) => (msg.id === '__stream__' ? { ...msg, content: `请求失败：${errorMessage}` } : msg)));
    }
  };

  return (
    <main style={styles.page}>
      <header style={styles.header}>
        <div>
          <h1 style={styles.title}>NL2SQL 智能分析</h1>
          <p style={styles.subtitle}>本项目仅支持自然语言转 SQL 数据分析</p>
        </div>
        <div style={styles.badge}>当前会话：{activeSession?.title ?? '无'}</div>
      </header>

      <section style={styles.settingsPanel}>
        <div style={styles.settingsHeader}>分析配置</div>
        <div style={styles.noticeBar}>本项目仅支持自然语言转 SQL 分析，请输入数据查询问题。</div>
        <div style={{ ...styles.settingsGrid, gridTemplateColumns: isMobile ? '1fr' : 'repeat(3, minmax(0, 1fr))' }}>
          <label style={styles.settingItem}>
            <span style={styles.settingLabel}>模型（NL2SQL 推理）</span>
            <select style={styles.input} value={selectedModel} onChange={(e) => setSelectedModel(e.target.value)}>
              {MODEL_OPTIONS.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label style={styles.settingItem}>
            <span style={styles.settingLabel}>Base URL（可选）</span>
            <input style={styles.input} value={vendorBaseUrl} onChange={(e) => setVendorBaseUrl(e.target.value)} />
          </label>
          <label style={styles.settingItem}>
            <span style={styles.settingLabel}>API Key（没有则无法调用外部模型）</span>
            <input
              style={styles.input}
              type="text"
              value={vendorApiKey}
              onChange={(e) => {
                const next = e.target.value;
                setVendorApiKeyPlain(next === '******' ? vendorApiKeyPlain : next);
                if (next !== '******') {
                  setVendorApiKeyPlain(next);
                }
              }}
              placeholder="输入后会显示为 ******"
            />
            {inlineError ? <span style={styles.inlineError}>{inlineError}</span> : null}
          </label>
        </div>
      </section>

      <section style={{ ...styles.grid, gridTemplateColumns: isMobile ? '1fr' : '280px minmax(0, 1fr) 320px' }}>
        <aside style={styles.panel}>
          <div style={styles.panelHead}>
            <h2 style={styles.panelTitle}>会话</h2>
            <button style={styles.smallButton} onClick={addSession} disabled={isCreatingSession}>新建</button>
          </div>
          <div style={styles.sectionDivider} />
          <ul style={styles.list}>
            {sessions.map((session) => (
              <li key={session.id} style={styles.listItem}>
                {editingSessionId === session.id ? (
                  <div style={styles.editRow}>
                    <input style={styles.input} value={editingTitle} onChange={(e) => setEditingTitle(e.target.value)} />
                    <button style={styles.smallButton} onClick={confirmEdit}>保存</button>
                  </div>
                ) : (
                  <>
                    <button style={styles.sessionButton} onClick={() => setActiveSession(session.id)}>
                      <span>{session.title}</span>
                      <span style={session.status === 'active' ? styles.activeTag : styles.idleTag}>
                        {session.status === 'active' ? '当前' : '空闲'}
                      </span>
                    </button>
                    <div style={styles.actionRow}>
                      <button style={styles.textButton} onClick={() => startEdit(session)}>重命名</button>
                      <button style={styles.textButton} onClick={() => removeSession(session.id)}>删除</button>
                    </div>
                  </>
                )}
              </li>
            ))}
          </ul>
        </aside>

        <section style={styles.panel}>
          <h2 style={styles.panelTitle}>问题输入</h2>
          <div style={styles.sectionDivider} />
          <div style={styles.chatBox}>
            {messages.map((message) => (
              <div key={message.id} style={message.role === 'user' ? styles.userBubble : styles.assistantBubble}>
                <strong>{message.role === 'user' ? '用户' : '助手'}：</strong>
                <span>{message.content}</span>
              </div>
            ))}
          </div>
          <div style={styles.inputRow}>
            <input
              style={styles.input}
              placeholder="请输入业务分析问题，例如：统计各区域销售额"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
            />
            <button style={styles.button} onClick={sendMessage}>发送</button>
          </div>
        </section>

        <aside style={styles.panel}>
          <h2 style={styles.panelTitle}>结果展示</h2>
          <div style={styles.sectionDivider} />

          <div style={styles.resultSection}>
            <div style={styles.resultSectionTitle}>结果提示</div>
            <div style={styles.resultHint}>{analysisResult?.answer_text || '暂无结果，请先输入分析问题。'}</div>
          </div>

          <div style={styles.resultSection}>
            <div style={styles.resultSectionTitle}>图表</div>
            <ChartPanel tableData={tableData} />
          </div>

          <div style={styles.resultSection}>
            <div style={styles.resultSectionTitle}>表格</div>
            <div style={styles.tablePlaceholder}>
              {tableData.length > 0 ? tableData.map(([name, value]) => `${name}: ${value}`).join(' | ') : '无数据'}
            </div>
          </div>

          <div style={styles.resultSection}>
            <div style={styles.resultSectionTitle}>生成的 SQL</div>
            <div style={styles.sqlBox}>
              <pre style={styles.sqlPre}>{generatedSql || '无 SQL'}</pre>
            </div>
          </div>
        </aside>
      </section>
    </main>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { minHeight: '100vh', padding: 24, background: '#f5f7fa', color: '#303133', fontFamily: 'Inter, system-ui, -apple-system, BlinkMacSystemFont, sans-serif', display: 'flex', flexDirection: 'column', overflow: 'hidden' },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18, flex: '0 0 auto', padding: '16px 20px', borderRadius: 12, background: '#fff', border: '1px solid #ebeef5' },
  title: { margin: 0, fontSize: 28, fontWeight: 700, color: '#303133' },
  subtitle: { margin: '8px 0 0', color: '#909399', fontSize: 13 },
  badge: { padding: '8px 14px', borderRadius: 999, background: '#ecf5ff', color: '#409eff', fontWeight: 600, border: '1px solid #d9ecff' },
  settingsPanel: { marginBottom: 16, padding: 16, borderRadius: 12, background: '#fff', border: '1px solid #ebeef5', flex: '0 0 auto' },
  settingsHeader: { fontSize: 16, fontWeight: 700, marginBottom: 12, color: '#303133' },
  noticeBar: { marginBottom: 12, padding: '10px 12px', borderRadius: 8, background: '#ecf5ff', color: '#409eff', border: '1px solid #d9ecff', fontSize: 13 },
  sectionDivider: { height: 1, background: '#ebeef5', margin: '12px 0' },
  settingsGrid: { display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 12 },
  settingsGridMobile: { display: 'grid', gridTemplateColumns: '1fr', gap: 12 },
  settingItem: { display: 'grid', gap: 6 },
  settingLabel: { fontSize: 13, fontWeight: 600, color: '#606266' },
  grid: { display: 'grid', gridTemplateColumns: '280px minmax(0, 1fr) 320px', gap: 16, flex: '1 1 auto', minHeight: 0, overflow: 'hidden' },
  mobileGrid: { display: 'grid', gridTemplateColumns: '1fr', gap: 16, flex: '1 1 auto', minHeight: 0, overflow: 'hidden' },
  panel: { background: '#fff', borderRadius: 12, padding: 16, border: '1px solid #ebeef5', minHeight: 0, height: '100%', overflowY: 'auto', overflowX: 'hidden' },
  panelHead: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 },
  panelTitle: { margin: 0, fontSize: 16, fontWeight: 700, color: '#303133' },
  list: { listStyle: 'none', padding: 0, margin: 0, display: 'grid', gap: 12 },
  listItem: { padding: 12, borderRadius: 10, background: '#f9fafc', border: '1px solid #ebeef5' },
  sessionButton: { width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center', border: 'none', background: 'transparent', padding: 0, cursor: 'pointer', marginBottom: 8 },
  actionRow: { display: 'flex', gap: 12 },
  editRow: { display: 'flex', gap: 8 },
  smallButton: { border: '1px solid #409eff', borderRadius: 8, padding: '8px 12px', background: '#409eff', color: '#fff', cursor: 'pointer' },
  textButton: { border: 'none', background: 'transparent', color: '#409eff', cursor: 'pointer', padding: 0 },
  activeTag: { fontSize: 12, color: '#67c23a', background: '#f0f9eb', padding: '4px 8px', borderRadius: 999, border: '1px solid #e1f3d8' },
  idleTag: { fontSize: 12, color: '#909399', background: '#f4f4f5', padding: '4px 8px', borderRadius: 999, border: '1px solid #e9e9eb' },
  chatBox: { display: 'grid', gap: 12, marginBottom: 16, minHeight: 360 },
  userBubble: { background: '#ecf5ff', padding: 14, borderRadius: 12, alignSelf: 'flex-end', border: '1px solid #d9ecff' },
  assistantBubble: { background: '#f5f7fa', padding: 14, borderRadius: 12, border: '1px solid #ebeef5' },
  inputRow: { display: 'flex', gap: 12 },
  input: { flex: 1, border: '1px solid #dcdfe6', borderRadius: 8, padding: '12px 14px', fontSize: 14, background: '#fff', color: '#303133' },
  button: { border: '1px solid #409eff', borderRadius: 8, padding: '12px 18px', background: '#409eff', color: '#fff', fontWeight: 600, cursor: 'pointer' },
  chartToolbar: { display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' },
  chartButton: { border: '1px solid #dcdfe6', background: '#fff', color: '#606266', borderRadius: 8, padding: '8px 12px', cursor: 'pointer' },
  chartButtonActive: { border: '1px solid #409eff', background: '#ecf5ff', color: '#409eff', borderRadius: 8, padding: '8px 12px', cursor: 'pointer' },
  chart: { height: 260, borderRadius: 12, marginBottom: 12, background: '#fff', border: '1px solid #ebeef5' },
  emptyState: { height: 260, borderRadius: 12, marginBottom: 12, background: '#fff', border: '1px solid #ebeef5', display: 'grid', placeItems: 'center', color: '#909399' },
  dataTable: { display: 'grid', gap: 8, borderRadius: 12, background: '#fff', border: '1px solid #ebeef5', padding: 12, marginBottom: 12 },
  resultSection: { marginBottom: 14 },
  resultSectionTitle: { fontSize: 14, fontWeight: 700, color: '#303133', marginBottom: 8 },
  resultHint: { border: '1px solid #ebeef5', borderRadius: 12, padding: 12, background: '#f9fafc', color: '#606266' },
  dataTableHeader: { display: 'grid', gridTemplateColumns: '1fr 120px', fontWeight: 700, color: '#303133' },
  dataTableRow: { display: 'grid', gridTemplateColumns: '1fr 120px', color: '#606266' },
  tablePlaceholder: { height: 120, borderRadius: 12, background: '#fff', border: '1px solid #ebeef5', display: 'grid', placeItems: 'center', color: '#909399', padding: 12, textAlign: 'center' },
  sqlBox: { marginTop: 12, borderRadius: 12, background: '#fff', color: '#303133', padding: 12, border: '1px solid #ebeef5' },
  sqlTitle: { fontSize: 14, fontWeight: 700, marginBottom: 8 },
  sqlPre: { margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontSize: 12, lineHeight: 1.5, color: '#606266' },
  inlineError: { color: '#f56c6c', fontSize: 12, marginTop: 4 },
};

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
