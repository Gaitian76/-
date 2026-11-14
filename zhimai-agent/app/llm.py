import json
import urllib.error
import urllib.request


class ModelError(Exception):
    pass


def chat(provider, messages, temperature=0.2, top_p=0.9):
    if not all(provider.values()):
        raise ModelError('模型服务尚未配置。请在 .env 中填写服务地址、API 密钥和模型名称。')
    base = provider['base_url'].rstrip('/')
    if not base.startswith('https://') and not base.startswith('http://127.0.0.1') and not base.startswith('http://localhost'):
        raise ModelError('模型服务地址应使用 HTTPS；本机服务可使用 HTTP。')
    url = base if base.endswith('/chat/completions') else base + '/chat/completions'
    payload = json.dumps({'model': provider['model'], 'messages': messages,
                          'temperature': temperature, 'top_p': top_p}, ensure_ascii=False).encode('utf-8')
    request = urllib.request.Request(url, data=payload, method='POST', headers={
        'Authorization': 'Bearer ' + provider['api_key'], 'Content-Type': 'application/json',
    })
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            data = json.load(response)
        answer = data['choices'][0]['message']['content']
        if not isinstance(answer, str) or not answer.strip():
            raise ModelError('模型没有返回文本，请检查服务配置。')
        return answer.strip()
    except urllib.error.HTTPError as exc:
        raise ModelError(f'模型服务返回 HTTP {exc.code}，请检查密钥、模型名称和服务地址。') from exc
    except (urllib.error.URLError, TimeoutError, KeyError, IndexError, ValueError) as exc:
        raise ModelError('无法连接模型服务或解析回复，请检查服务地址和模型配置。') from exc
