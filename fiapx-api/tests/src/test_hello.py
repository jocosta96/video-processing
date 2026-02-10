import pytest
import src.hello

@pytest.mark.unit
def test_hello():
    result = src.hello.hello()
    assert result == 'hello world'