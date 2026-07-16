from cepe_fynsp.etl.normalize import parse_dollar_amounts, snake_case


def test_snake_case_program_int_area() -> None:
    assert snake_case("Program Int. Area") == "program_int_area"


def test_parse_dollar_amounts() -> None:
    parsed = parse_dollar_amounts(["1,000", "(2,500)", ""])
    assert parsed.iloc[0] == 1000
    assert parsed.iloc[1] == -2500
    assert parsed.isna().iloc[2]
