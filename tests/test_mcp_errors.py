from src.mcp.errors import AIRWaveMcpError


def test_airwave_mcp_error_string_representation() -> None:
    err = AIRWaveMcpError(code="E_TEST", message="boom", details={"k": "v"})

    assert str(err) == "E_TEST: boom"
    assert err.details == {"k": "v"}
