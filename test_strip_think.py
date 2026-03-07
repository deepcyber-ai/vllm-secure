from filter_proxy import strip_think

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
