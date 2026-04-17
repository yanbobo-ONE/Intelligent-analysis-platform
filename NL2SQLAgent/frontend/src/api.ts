export type HealthResponse = {
  status: string;
};

export type Session = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
};

export type ChatResponse = {
  answer_text: string;
  table_data: Array<Record<string, unknown>>;
  chart_spec: {
    type: string;
    xField: string;
    yField: string;
    seriesField: string;
  };
  trace: {
    model: string;
    latencyMs: number;
    toolCalls?: unknown[];
    streaming?: boolean;
  };
};

const DEFAULT_BASE_URL = 'http://127.0.0.1:8010';

export async function getHealth(baseUrl = DEFAULT_BASE_URL): Promise<HealthResponse> {
  const response = await fetch(`${baseUrl}/health`);
  if (!response.ok) {
    throw new Error('health check failed');
  }
  return response.json() as Promise<HealthResponse>;
}

export async function listSessions(baseUrl = DEFAULT_BASE_URL): Promise<Session[]> {
  const response = await fetch(`${baseUrl}/api/sessions`);
  if (!response.ok) {
    throw new Error('list sessions failed');
  }
  return response.json() as Promise<Session[]>;
}

export async function createSession(title: string, baseUrl = DEFAULT_BASE_URL): Promise<Session> {
  const response = await fetch(`${baseUrl}/api/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  });
  if (!response.ok) {
    throw new Error('create session failed');
  }
  return response.json() as Promise<Session>;
}

export async function chat(message: string, sessionId: string, baseUrl = DEFAULT_BASE_URL): Promise<ChatResponse> {
  const response = await fetch(`${baseUrl}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sessionId, message }),
  });
  if (!response.ok) {
    throw new Error('chat failed');
  }
  return response.json() as Promise<ChatResponse>;
}
