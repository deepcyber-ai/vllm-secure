from filter_proxy import strip_think, extract_first_json, clean_content

# ── strip_think tests ────────────────────────────────────────────────

def test_no_tags():
    assert strip_think("Hello world") == "Hello world"

def test_single_block():
    assert strip_think("<think>reasoning</think>The answer") == "The answer"

def test_multiple_blocks():
    assert strip_think("<think>a</think>one<think>b</think>two") == "onetwo"

def test_multiline():
    text = "<think>\nstep 1\nstep 2\n</think>Result"
    assert strip_think(text) == "Result"

def test_unclosed_tag():
    assert strip_think("Answer<think>never closes") == "Answer"

def test_empty_tags():
    assert strip_think("<think></think>Clean") == "Clean"

def test_json_inside_think():
    text = '<think>{"step": 1}</think>{"result": "ok"}'
    assert strip_think(text) == '{"result": "ok"}'

def test_only_think():
    assert strip_think("<think>nothing useful</think>") == ""

def test_none():
    assert strip_think(None) is None

def test_empty():
    assert strip_think("") == ""


# ── extract_first_json tests ────────────────────────────────────────

def test_json_valid_passthrough():
    """Already-valid JSON passes through unchanged."""
    text = '{"score_value": "True", "description": "test", "rationale": "ok"}'
    assert extract_first_json(text) == text

def test_json_trailing_garbage():
    """Repeated metadata blocks after valid JSON are stripped."""
    valid = '{"score_value": "True", "description": "test", "rationale": "ok"}'
    garbage = ', "metadata": "extra", "metadata": "more extra"'
    assert extract_first_json(valid + garbage) == valid

def test_json_multiple_objects():
    """Only the first JSON object is returned when model emits multiple."""
    first = '{"score_value": "True", "description": "test", "rationale": "ok"}'
    second = ' {"final_response": "blah", "final_score": "True"}'
    assert extract_first_json(first + second) == first

def test_json_with_nested_braces():
    """Nested objects inside the first JSON are preserved."""
    text = '{"result": {"inner": "value"}, "list": [1, 2]} extra garbage'
    assert extract_first_json(text) == '{"result": {"inner": "value"}, "list": [1, 2]}'

def test_json_with_escaped_quotes():
    """Escaped quotes inside strings don't break brace tracking."""
    text = '{"msg": "he said \\"hello\\""} trailing'
    assert extract_first_json(text) == '{"msg": "he said \\"hello\\""}'

def test_json_with_braces_in_strings():
    """Braces inside quoted strings don't affect depth tracking."""
    text = '{"pattern": "if (x) { y }"} extra'
    assert extract_first_json(text) == '{"pattern": "if (x) { y }"}'

def test_plain_text_passthrough():
    """Non-JSON text passes through unchanged."""
    text = "This is a normal response about investing."
    assert extract_first_json(text) == text

def test_json_none():
    assert extract_first_json(None) is None

def test_json_empty():
    assert extract_first_json("") == ""

def test_json_whitespace_prefix():
    """Leading whitespace before JSON is handled."""
    text = '  {"score_value": "False"} garbage'
    assert extract_first_json(text) == '{"score_value": "False"}'

def test_json_truncated():
    """Truncated JSON (no closing brace) returns original."""
    text = '{"score_value": "True", "description": "te'
    assert extract_first_json(text) == text

def test_deepseek_r1_scorer_ramble():
    """Real-world DeepSeek-R1 scorer output with repeated metadata."""
    text = (
        '{"score_value": "True", "description": "The response provides personalised '
        'financial advice", "rationale": "It recommended a specific fund allocation"}'
        ', "metadata": "analysis complete", "metadata": "final assessment", '
        '"metadata": "scoring done", "metadata": "evaluation finished", '
        '"metadata": "review complete"'
    )
    expected = (
        '{"score_value": "True", "description": "The response provides personalised '
        'financial advice", "rationale": "It recommended a specific fund allocation"}'
    )
    assert extract_first_json(text) == expected


# ── clean_content (combined pipeline) tests ──────────────────────────

def test_clean_think_then_json():
    """Think tags stripped first, then JSON extracted."""
    text = (
        '<think>Let me analyze this response...</think>'
        '{"score_value": "False", "description": "ok", "rationale": "safe"}'
        ', "metadata": "done"'
    )
    expected = '{"score_value": "False", "description": "ok", "rationale": "safe"}'
    assert clean_content(text) == expected

def test_clean_plain_text():
    """Plain text with think tags but no JSON."""
    text = "<think>reasoning</think>The answer is 42."
    assert clean_content(text) == "The answer is 42."
