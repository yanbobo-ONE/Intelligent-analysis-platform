from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.database import init_db
from app.main import app

init_db()
client = TestClient(app)


def test_session_crud() -> None:
    created = client.post('/api/sessions', json={'title': '测试会话'})
    assert created.status_code == 200
    session = created.json()
    session_id = session['id']

    listed = client.get('/api/sessions')
    assert listed.status_code == 200
    assert any(item['id'] == session_id for item in listed.json())

    updated = client.patch(f'/api/sessions/{session_id}', json={'title': '已更新会话'})
    assert updated.status_code == 200
    assert updated.json()['title'] == '已更新会话'

    deleted = client.delete(f'/api/sessions/{session_id}')
    assert deleted.status_code == 200
    assert deleted.json()['deleted'] is True


def test_chat_routes_general_input_returns_nl2sql_only_notice() -> None:
    created = client.post('/api/sessions', json={'title': '聊天会话'})
    session_id = created.json()['id']

    response = client.post('/api/chat', json={'sessionId': session_id, 'message': '你是什么模型', 'model': 'qwen3-max'})
    assert response.status_code == 200
    payload = response.json()
    assert payload['trace']['sql'] == ''
    assert payload['trace']['streaming'] is False
    assert '仅支持 NL2SQL' in payload['answer_text']


def test_chat_routes_limit_hint(monkeypatch) -> None:
    created = client.post('/api/sessions', json={'title': '分析会话'})
    session_id = created.json()['id']

    from app.services import chat_service

    captured = {}

    class DummyLLM:
        def invoke(self, prompt: str):
            captured['prompt'] = prompt
            return SimpleNamespace(content='SELECT region, SUM(amount) AS total_amount FROM sales_demo GROUP BY region ORDER BY total_amount DESC LIMIT 2;')

    monkeypatch.setattr(chat_service, '_get_chat_llm', lambda **kwargs: DummyLLM())

    response = client.post('/api/chat', json={'sessionId': session_id, 'message': '按销售额从高到低返回前2条', 'model': 'qwen3-max'})
    assert response.status_code == 200
    payload = response.json()
    assert '只返回前 2 条' in captured['prompt']
    assert 'LIMIT 2' in payload['trace']['sql'] or 'LIMIT 3' not in payload['trace']['sql']
    assert len(payload['table_data']) == 2


def test_general_chat_returns_nl2sql_only_notice_for_followup() -> None:
    created = client.post('/api/sessions', json={'title': '记忆会话'})
    session_id = created.json()['id']

    first = client.post('/api/chat', json={'sessionId': session_id, 'message': '你好', 'model': 'qwen3-max'})
    assert first.status_code == 200

    response = client.post('/api/chat', json={'sessionId': session_id, 'message': '你支持什么能力', 'model': 'qwen3-max'})
    assert response.status_code == 200
    payload = response.json()
    assert '仅支持 NL2SQL' in payload['answer_text']


def test_sql_safety_helper() -> None:
    from app.services.security_service import validate_readonly_sql

    validate_readonly_sql('SELECT * FROM demo')

    try:
        validate_readonly_sql('DROP TABLE demo')
    except ValueError as exc:
        assert 'Forbidden SQL keyword' in str(exc) or 'Only SELECT/WITH' in str(exc)
    else:
        raise AssertionError('expected ValueError')
