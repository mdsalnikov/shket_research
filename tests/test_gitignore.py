def test_gitignore_contains_ghtoken():
    with open(".gitignore", "r") as f:
        content = f.read()
    assert "GHTOKEN" in content, "GHTOKEN entry missing in .gitignore"
