def test_tidy_stdin_is_formatted_to_stdout(run_sxpb_tidy_tool):
    result = run_sxpb_tidy_tool(["-"], stdin_data="  ( name value); note\n")

    assert result.returncode == 0
    assert result.stdout == "(name value) ; note\n"
    assert result.stderr == ""


def test_lint_stdin_reports_finding_without_output(run_sxpb_lint_tool):
    result = run_sxpb_lint_tool(["-"], stdin_data="( name value)\n")

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == "Needs tidying: -\n"


def test_lint_clean_stdin_succeeds(run_sxpb_lint_tool):
    result = run_sxpb_lint_tool(["-"], stdin_data="(name value)\n")

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_tidy_no_paths_formats_current_directory(run_sxpb_tidy_tool, tmp_path):
    path = tmp_path / "example.sxpb"
    path.write_text(" ( name value)\n")

    result = run_sxpb_tidy_tool([], cwd=tmp_path)

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == "Tidied: example.sxpb\n"
    assert path.read_text() == "(name value)\n"


def test_tidy_rewrites_file(run_sxpb_tidy_tool, tmp_path):
    path = tmp_path / "example.sxpb"
    path.write_text(" ( name value)\n")

    result = run_sxpb_tidy_tool([str(path)])

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == f"Tidied: {path}\n"
    assert path.read_text() == "(name value)\n"


def test_lint_does_not_rewrite_file(run_sxpb_lint_tool, tmp_path):
    path = tmp_path / "example.sxpb"
    path.write_text("( name value)\n")

    result = run_sxpb_lint_tool([str(path)])

    assert result.returncode == 1
    assert result.stderr == f"Needs tidying: {path}\n"
    assert path.read_text() == "( name value)\n"


def test_tidy_directory_recurses_over_sxpb_files_only(run_sxpb_tidy_tool, tmp_path):
    nested = tmp_path / "nested"
    nested.mkdir()
    sxpb_path = nested / "data.sxpb"
    sxpb_path.write_text("( item value)\n")
    ignored_path = nested / "notes.txt"
    ignored_path.write_text("( item value)\n")

    result = run_sxpb_tidy_tool([str(tmp_path)])

    assert result.returncode == 0
    assert sxpb_path.read_text() == "(item value)\n"
    assert ignored_path.read_text() == "( item value)\n"


def test_tidy_validates_all_files_before_writing(run_sxpb_tidy_tool, tmp_path):
    dirty_path = tmp_path / "a.sxpb"
    dirty_path.write_text("( item value)\n")
    invalid_path = tmp_path / "b.sxpb"
    invalid_path.write_text("(unclosed\n")

    result = run_sxpb_tidy_tool([str(tmp_path)])

    assert result.returncode == 2
    assert "Unclosed opening parenthesis" in result.stderr
    assert dirty_path.read_text() == "( item value)\n"


def test_stdin_cannot_be_combined_with_paths(run_sxpb_tidy_tool, tmp_path):
    path = tmp_path / "data.sxpb"
    path.write_text("(item value)\n")

    result = run_sxpb_tidy_tool(["-", str(path)], stdin_data="")

    assert result.returncode == 2
    assert "cannot be combined" in result.stderr


def test_ignore_file_excludes_matching_files_and_directories(
    run_sxpb_tidy_tool, tmp_path
):
    ignored_directory = tmp_path / "generated"
    ignored_directory.mkdir()
    ignored_nested_path = ignored_directory / "nested.sxpb"
    ignored_nested_path.write_text("( ignored nested)\n")
    ignored_file_path = tmp_path / "ignored.sxpb"
    ignored_file_path.write_text("( ignored file)\n")
    source_path = tmp_path / "source.sxpb"
    source_path.write_text("( source value)\n")
    ignore_path = tmp_path / ".gitignore"
    ignore_path.write_text("/generated/\n/ignored.sxpb\n")

    result = run_sxpb_tidy_tool(["--ignore-file", ".gitignore"], cwd=tmp_path)

    assert result.returncode == 0
    assert source_path.read_text() == "(source value)\n"
    assert ignored_nested_path.read_text() == "( ignored nested)\n"
    assert ignored_file_path.read_text() == "( ignored file)\n"
    assert result.stderr == "Tidied: source.sxpb\n"


def test_ignore_file_negation_reincludes_file(run_sxpb_tidy_tool, tmp_path):
    ignored_path = tmp_path / "ignored.sxpb"
    ignored_path.write_text("( ignored value)\n")
    included_path = tmp_path / "included.sxpb"
    included_path.write_text("( included value)\n")
    ignore_path = tmp_path / ".gitignore"
    ignore_path.write_text("*.sxpb\n!/included.sxpb\n")

    result = run_sxpb_tidy_tool(["--ignore-file", ".gitignore"], cwd=tmp_path)

    assert result.returncode == 0
    assert ignored_path.read_text() == "( ignored value)\n"
    assert included_path.read_text() == "(included value)\n"


def test_ignore_patterns_are_relative_to_ignore_file(run_sxpb_tidy_tool, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    ignored_path = project / "ignored.sxpb"
    ignored_path.write_text("( ignored value)\n")
    source_path = project / "source.sxpb"
    source_path.write_text("( source value)\n")
    ignore_path = project / ".gitignore"
    ignore_path.write_text("/ignored.sxpb\n")

    result = run_sxpb_tidy_tool(
        ["--ignore-file", str(ignore_path), str(project)], cwd=tmp_path
    )

    assert result.returncode == 0
    assert ignored_path.read_text() == "( ignored value)\n"
    assert source_path.read_text() == "(source value)\n"


def test_ignore_file_applies_to_explicit_file(run_sxpb_tidy_tool, tmp_path):
    ignored_path = tmp_path / "ignored.sxpb"
    ignored_path.write_text("( ignored value)\n")
    ignore_path = tmp_path / ".gitignore"
    ignore_path.write_text("/ignored.sxpb\n")

    result = run_sxpb_tidy_tool(["--ignore-file", str(ignore_path), str(ignored_path)])

    assert result.returncode == 0
    assert result.stderr == ""
    assert ignored_path.read_text() == "( ignored value)\n"


def test_lint_respects_ignore_file(run_sxpb_lint_tool, tmp_path):
    ignored_path = tmp_path / "ignored.sxpb"
    ignored_path.write_text("( ignored value)\n")
    ignore_path = tmp_path / ".gitignore"
    ignore_path.write_text("/ignored.sxpb\n")

    result = run_sxpb_lint_tool(["--ignore-file", ".gitignore"], cwd=tmp_path)

    assert result.returncode == 0
    assert result.stderr == ""


def test_no_implicit_hidden_directory_exclusion(run_sxpb_tidy_tool, tmp_path):
    hidden = tmp_path / ".hidden"
    hidden.mkdir()
    path = hidden / "source.sxpb"
    path.write_text("( source value)\n")

    result = run_sxpb_tidy_tool([], cwd=tmp_path)

    assert result.returncode == 0
    assert path.read_text() == "(source value)\n"


def test_missing_ignore_file_is_reported(run_sxpb_tidy_tool, tmp_path):
    result = run_sxpb_tidy_tool(["--ignore-file", "missing.gitignore"], cwd=tmp_path)

    assert result.returncode == 2
    assert result.stderr == (
        "sxpb-tidy: Ignore file does not exist: missing.gitignore\n"
    )


def test_invalid_ignore_file_is_reported(run_sxpb_lint_tool, tmp_path):
    ignore_path = tmp_path / ".gitignore"
    ignore_path.write_text("!\n")

    result = run_sxpb_lint_tool(["--ignore-file", ".gitignore"], cwd=tmp_path)

    assert result.returncode == 2
    assert "sxpb-lint: Invalid git pattern" in result.stderr


def test_tidy_has_no_check_option(run_sxpb_tidy_tool):
    result = run_sxpb_tidy_tool(["--check"])

    assert result.returncode == 2
    assert "unrecognized arguments: --check" in result.stderr


def test_lint_has_no_check_option(run_sxpb_lint_tool):
    result = run_sxpb_lint_tool(["--check"])

    assert result.returncode == 2
    assert "unrecognized arguments: --check" in result.stderr
