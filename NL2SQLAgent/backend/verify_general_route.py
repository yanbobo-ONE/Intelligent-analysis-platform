from types import SimpleNamespace

from app.services import chat_service


class DummyLLM:
    def invoke(self, prompt):
        return SimpleNamespace(content='我是模型回答，不走SQL。')


chat_service._get_chat_llm = lambda **kwargs: DummyLLM()
resp = chat_service.build_response('你是什么模型', model_name='qwen3-max')
print(resp['answer_text'])
print('SQL=', repr(resp['trace']['sql']))
print('streaming=', resp['trace']['streaming'])
