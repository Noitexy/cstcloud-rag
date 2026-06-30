from app.clients.cstcloud_client import CSTCloudClient


def test_r1_messages_are_merged_to_user_role():
    messages = [{"role": "system", "content": "规则"}, {"role": "user", "content": "问题"}]
    result = CSTCloudClient.compatible_messages("deepseek-r1:32b", messages)
    assert len(result) == 1
    assert result[0]["role"] == "user"
    assert "规则" in result[0]["content"]


def test_model_specific_thinking_kwargs():
    assert CSTCloudClient.thinking_kwargs("qwen3:235b", False) == {
        "chat_template_kwargs": {"enable_thinking": False}
    }
    assert CSTCloudClient.thinking_kwargs("deepseek-v4-flash", True) == {
        "chat_template_kwargs": {"thinking": True}
    }
