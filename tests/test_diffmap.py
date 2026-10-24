"""Acceptance tests for Phase 1: Diff to changed symbols."""

from pathlib import Path
from ripple.diffmap import parse_diff


def test_body_change_maps_to_function(mini_app_repo: Path):
    """One-line edit inside a function -> exactly that qualname."""
    pricing_file = mini_app_repo / "pricing.py"
    content = pricing_file.read_text(encoding="utf-8")
    new_content = content.replace(
        "return price * (1.0 - discount)",
        "return price * (1.0 - discount) + 0.0",
    )
    pricing_file.write_text(new_content, encoding="utf-8")

    symbols = parse_diff(mini_app_repo)
    assert len(symbols) == 1
    assert symbols[0].qualname == "apply_discount"
    assert symbols[0].kind == "function"
    assert symbols[0].file.replace("\\", "/") == "pricing.py"


def test_method_in_class_gets_qualified_name(mini_app_repo: Path):
    """Edit in a method -> Class.method."""
    cart_file = mini_app_repo / "cart.py"
    content = cart_file.read_text(encoding="utf-8")
    new_content = content.replace(
        "self.items.append",
        "# log item\n            self.items.append",
    )
    cart_file.write_text(new_content, encoding="utf-8")

    symbols = parse_diff(mini_app_repo)
    qualnames = [s.qualname for s in symbols]
    assert "Cart.add_item" in qualnames
    assert any(s.kind == "method" for s in symbols if s.qualname == "Cart.add_item")


def test_added_and_deleted_function(mini_app_repo: Path):
    """Both added and deleted functions reported with kind added/deleted."""
    utils_file = mini_app_repo / "utils.py"
    # Delete format_currency and add new_helper
    new_content = '"""Utility formatting functions for mini_app."""\n\ndef new_helper(val: int) -> int:\n    return val * 2\n'
    utils_file.write_text(new_content, encoding="utf-8")

    symbols = parse_diff(mini_app_repo)
    kinds_by_qualname = {s.qualname: s.kind for s in symbols}
    assert "new_helper" in kinds_by_qualname
    assert kinds_by_qualname["new_helper"] == "added"
    assert "format_currency" in kinds_by_qualname
    assert kinds_by_qualname["format_currency"] == "deleted"


def test_comment_only_change_is_ast_equal(mini_app_repo: Path):
    """ast_equal == True for comment-only change."""
    pricing_file = mini_app_repo / "pricing.py"
    content = pricing_file.read_text(encoding="utf-8")
    new_content = content.replace(
        "return price * tax_rate",
        "# calculating tax\n    return price * tax_rate",
    )
    pricing_file.write_text(new_content, encoding="utf-8")

    symbols = parse_diff(mini_app_repo)
    assert len(symbols) == 1
    assert symbols[0].qualname == "calculate_tax"
    assert symbols[0].ast_equal is True


def test_docstring_only_change_is_ast_equal(mini_app_repo: Path):
    """ast_equal == True for docstring-only change."""
    pricing_file = mini_app_repo / "pricing.py"
    content = pricing_file.read_text(encoding="utf-8")
    new_content = content.replace(
        '"""Calculate tax for price."""',
        '"""Calculate sales tax for the given price item."""',
    )
    pricing_file.write_text(new_content, encoding="utf-8")

    symbols = parse_diff(mini_app_repo)
    assert len(symbols) == 1
    assert symbols[0].qualname == "calculate_tax"
    assert symbols[0].ast_equal is True


def test_module_level_change(mini_app_repo: Path):
    """Symbol is the module for top-level code edits."""
    pricing_file = mini_app_repo / "pricing.py"
    content = pricing_file.read_text(encoding="utf-8")
    new_content = "DEFAULT_TAX_RATE = 0.15\n" + content
    pricing_file.write_text(new_content, encoding="utf-8")

    symbols = parse_diff(mini_app_repo)
    mod_syms = [s for s in symbols if s.kind == "module"]
    assert len(mod_syms) >= 1
    assert mod_syms[0].qualname == "pricing"


def test_multi_hunk_multi_file(mini_app_repo: Path):
    """Symbols from two files, no duplicates."""
    pricing_file = mini_app_repo / "pricing.py"
    inventory_file = mini_app_repo / "inventory.py"

    pricing_file.write_text(
        pricing_file.read_text(encoding="utf-8").replace("price * tax_rate", "price * tax_rate + 0.01"),
        encoding="utf-8",
    )
    inventory_file.write_text(
        inventory_file.read_text(encoding="utf-8").replace("return _STOCK.get(item_id, 0)", "return _STOCK.get(item_id, -1)"),
        encoding="utf-8",
    )

    symbols = parse_diff(mini_app_repo)
    qualnames = [s.qualname for s in symbols]
    # No duplicate qualnames per file
    keys = [(s.file, s.qualname) for s in symbols]
    assert len(keys) == len(set(keys))
    assert "calculate_tax" in qualnames
    assert "check_stock" in qualnames


def test_non_python_file_ignored(mini_app_repo: Path):
    """README edit -> []."""
    readme_file = mini_app_repo / "README.md"
    readme_file.write_text("# Documentation update\n", encoding="utf-8")

    symbols = parse_diff(mini_app_repo)
    assert symbols == []
