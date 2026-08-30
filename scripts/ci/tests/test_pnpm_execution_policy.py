from __future__ import annotations

import ast
import json
import re
import shlex
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = ROOT / ".github" / "workflows"
SCRIPT_REFERENCE = re.compile(r"(?<![\w./-])scripts/[\w./-]+[.](?:js|mjs|py|sh)\b")
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=.*", re.DOTALL)
JS_DIRECT_PNPM = re.compile(r"\b(?:execFile|execFileSync|spawn|spawnSync)\s*\(\s*['\"]pnpm['\"]")
JS_SHELL_PNPM = re.compile(r"\b(?:exec|execSync)\s*\(\s*['\"]pnpm(?:\s|['\"])")
PYTHON_PROCESS_CALLS = {
    "call",
    "check_call",
    "check_output",
    "popen",
    "Popen",
    "run",
    "system",
}


@dataclass(frozen=True, order=True)
class PackageScript:
    manifest: Path
    name: str


def active_manifests(root: Path = ROOT) -> tuple[Path, ...]:
    """Return production pnpm-workspace manifests, excluding protected legacy POC fixtures."""

    manifests = [root / "package.json"]
    for workspace in ("apps", "packages"):
        manifests.extend(sorted((root / workspace).glob("*/package.json")))
    return tuple(manifests)


def manifest_document(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def shell_segments(command: str) -> tuple[tuple[str, ...], ...]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()")
    lexer.whitespace_split = True
    lexer.commenters = "#"
    segments: list[tuple[str, ...]] = []
    current: list[str] = []
    for token in lexer:
        if token and all(character in ";&|()" for character in token):
            if current:
                segments.append(tuple(current))
                current = []
        else:
            current.append(token)
    if current:
        segments.append(tuple(current))
    return tuple(segments)


def command_executable(tokens: tuple[str, ...]) -> tuple[int, str] | None:
    """Resolve the executable after shell assignment and standard command wrappers."""

    index = 0
    while index < len(tokens) and (tokens[index] == "!" or ASSIGNMENT.fullmatch(tokens[index])):
        index += 1
    while index < len(tokens) and tokens[index] in {"command", "env", "exec"}:
        wrapper = tokens[index]
        index += 1
        while index < len(tokens) and tokens[index].startswith("-"):
            index += 1
        if wrapper == "env":
            while index < len(tokens) and ASSIGNMENT.fullmatch(tokens[index]):
                index += 1
    if index >= len(tokens):
        return None
    return index, tokens[index]


def bare_shell_pnpm(command: str) -> tuple[str, ...]:
    violations: list[str] = []
    for segment in shell_segments(command):
        executable = command_executable(segment)
        if executable is not None and executable[1] == "pnpm":
            violations.append(shlex.join(segment))
    return tuple(violations)


def corepack_shell_calls(command: str) -> tuple[tuple[str, ...], ...]:
    calls: list[tuple[str, ...]] = []
    for segment in shell_segments(command):
        executable = command_executable(segment)
        if executable is None:
            continue
        index, name = executable
        if name == "corepack" and index + 1 < len(segment) and segment[index + 1] == "pnpm":
            calls.append(segment[index + 2 :])
    return tuple(calls)


def literal_command_vectors(source: str) -> tuple[tuple[str, ...], ...]:
    tree = ast.parse(source)
    vectors: set[tuple[str, ...]] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.List, ast.Tuple)) or not node.elts:
            continue
        if all(
            isinstance(element, ast.Constant) and isinstance(element.value, str)
            for element in node.elts
        ):
            values = tuple(element.value for element in node.elts)  # type: ignore[union-attr]
            executable = command_executable(values)
            if executable is not None and executable[1] in {"corepack", "pnpm"}:
                vectors.add(values)
    return tuple(sorted(vectors))


def python_literal_pnpm_calls(source: str) -> tuple[str, ...]:
    """Find directly executed pnpm strings, including shell-wrapper child processes."""

    tree = ast.parse(source)
    violations: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        function_name = (
            node.func.attr
            if isinstance(node.func, ast.Attribute)
            else node.func.id
            if isinstance(node.func, ast.Name)
            else ""
        )
        if function_name not in PYTHON_PROCESS_CALLS:
            continue
        argument = node.args[0]
        if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
            violations.update(bare_shell_pnpm(argument.value))
            continue
        if not isinstance(argument, (ast.List, ast.Tuple)) or not all(
            isinstance(element, ast.Constant) and isinstance(element.value, str)
            for element in argument.elts
        ):
            continue
        vector = tuple(element.value for element in argument.elts)  # type: ignore[union-attr]
        executable = command_executable(vector)
        if executable is not None and executable[1] == "pnpm":
            violations.add(shlex.join(vector))
        if executable is not None and executable[1] in {"bash", "sh", "zsh"}:
            for index, token in enumerate(vector):
                if token in {"-c", "-lc"} and index + 1 < len(vector):
                    violations.update(bare_shell_pnpm(vector[index + 1]))
    return tuple(sorted(violations))


def workflow_run_blocks(root: Path = ROOT) -> tuple[tuple[Path, str, str, str], ...]:
    blocks: list[tuple[Path, str, str, str]] = []
    for path in sorted((root / ".github" / "workflows").glob("*.y*ml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job_name, job in document.get("jobs", {}).items():
            for index, step in enumerate(job.get("steps", [])):
                command = step.get("run")
                if isinstance(command, str):
                    blocks.append((path, str(job_name), str(step.get("name", index)), command))
    return tuple(blocks)


def referenced_scripts(text: str, base: Path, root: Path = ROOT) -> tuple[Path, ...]:
    paths: set[Path] = set()
    for match in SCRIPT_REFERENCE.finditer(text):
        relative = Path(match.group())
        candidates = (base / relative, root / relative)
        resolved = next(
            (candidate.resolve() for candidate in candidates if candidate.is_file()), None
        )
        if resolved is not None:
            paths.add(resolved)
    return tuple(sorted(paths))


def resolve_package_call(
    arguments: tuple[str, ...],
    current_manifest: Path,
    manifests: tuple[Path, ...],
) -> tuple[PackageScript, ...]:
    by_name = {manifest_document(path).get("name"): path for path in manifests}
    selected: list[Path] = []
    recursive = False
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument in {"--filter", "-F"} and index + 1 < len(arguments):
            manifest = by_name.get(arguments[index + 1])
            if manifest is not None:
                selected.append(manifest)
            index += 2
            continue
        if argument in {"--recursive", "-r"}:
            recursive = True
            index += 1
            continue
        if argument in {"--if-present", "--silent"}:
            index += 1
            continue
        if argument.startswith("-"):
            index += 1
            continue
        break
    if index >= len(arguments):
        return ()
    command = arguments[index]
    if command == "run":
        index += 1
        while index < len(arguments) and arguments[index].startswith("-"):
            index += 1
        if index >= len(arguments):
            return ()
        command = arguments[index]
    targets = selected or (list(manifests) if recursive else [current_manifest])
    return tuple(
        PackageScript(manifest=manifest, name=command)
        for manifest in targets
        if command in manifest_document(manifest).get("scripts", {})
    )


def hosted_execution_graph(
    root: Path = ROOT,
) -> tuple[set[PackageScript], set[Path], list[tuple[str, str]]]:
    """Trace workflow commands through local scripts and pnpm package-script calls."""

    manifests = active_manifests(root)
    root_manifest = root / "package.json"
    package_queue: deque[PackageScript] = deque()
    source_queue: deque[Path] = deque()
    edges: list[tuple[str, str]] = []

    for workflow, job, step, command in workflow_run_blocks(root):
        origin = f"{workflow.relative_to(root)}:{job}:{step}"
        for arguments in corepack_shell_calls(command):
            for target in resolve_package_call(arguments, root_manifest, manifests):
                package_queue.append(target)
                edges.append((origin, f"{target.manifest.relative_to(root)}#{target.name}"))
        for script in referenced_scripts(command, root, root):
            source_queue.append(script)
            edges.append((origin, str(script.relative_to(root))))

    seen_sources: set[Path] = set()
    seen_packages: set[PackageScript] = set()
    while source_queue or package_queue:
        while source_queue:
            path = source_queue.popleft()
            if path in seen_sources:
                continue
            seen_sources.add(path)
            source = path.read_text(encoding="utf-8")
            base = path.parent if path.parent.name == "scripts" else root
            for nested in referenced_scripts(source, base, root):
                source_queue.append(nested)
                edges.append((str(path.relative_to(root)), str(nested.relative_to(root))))
            vectors = literal_command_vectors(source) if path.suffix == ".py" else ()
            calls = [
                vector[2:]
                for vector in vectors
                if len(vector) >= 2 and vector[:2] == ("corepack", "pnpm")
            ]
            if path.suffix == ".sh":
                calls.extend(corepack_shell_calls(source))
            for arguments in calls:
                for target in resolve_package_call(arguments, root_manifest, manifests):
                    package_queue.append(target)
                    edges.append(
                        (
                            str(path.relative_to(root)),
                            f"{target.manifest.relative_to(root)}#{target.name}",
                        )
                    )

        if not package_queue:
            continue
        target = package_queue.popleft()
        if target in seen_packages:
            continue
        seen_packages.add(target)
        manifest = manifest_document(target.manifest)
        scripts = manifest.get("scripts", {})
        command = scripts[target.name]
        for lifecycle_name in (f"pre{target.name}", f"post{target.name}"):
            if lifecycle_name in scripts:
                lifecycle = PackageScript(target.manifest, lifecycle_name)
                package_queue.append(lifecycle)
                edges.append(
                    (
                        f"{target.manifest.relative_to(root)}#{target.name}",
                        f"{target.manifest.relative_to(root)}#{lifecycle_name}",
                    )
                )
        for arguments in corepack_shell_calls(command):
            for nested in resolve_package_call(arguments, target.manifest, manifests):
                package_queue.append(nested)
                edges.append(
                    (
                        f"{target.manifest.relative_to(root)}#{target.name}",
                        f"{nested.manifest.relative_to(root)}#{nested.name}",
                    )
                )
        for script in referenced_scripts(command, target.manifest.parent, root):
            source_queue.append(script)
            edges.append(
                (
                    f"{target.manifest.relative_to(root)}#{target.name}",
                    str(script.relative_to(root)),
                )
            )

    return seen_packages, seen_sources, edges


def production_script_sources(root: Path = ROOT) -> tuple[Path, ...]:
    paths = set((root / "scripts").rglob("*"))
    for manifest in active_manifests(root):
        paths.update((manifest.parent / "scripts").rglob("*"))
    return tuple(
        sorted(
            path
            for path in paths
            if path.is_file()
            and "tests" not in path.relative_to(root).parts
            and path.suffix in {".js", ".mjs", ".py", ".sh"}
        )
    )


def test_shell_detector_accepts_corepack_and_rejects_global_pnpm() -> None:
    assert bare_shell_pnpm("corepack pnpm --filter @visualization-agent/web build") == ()
    assert bare_shell_pnpm("node tool.mjs --package-manager pnpm") == ()
    assert bare_shell_pnpm("pnpm build") == ("pnpm build",)
    assert bare_shell_pnpm("CI=true env -- pnpm test") == ("CI=true env -- pnpm test",)
    assert bare_shell_pnpm("node check.mjs && command pnpm audit") == ("command pnpm audit",)


def test_python_detector_accepts_corepack_and_rejects_global_pnpm() -> None:
    positive = literal_command_vectors('command = ("corepack", "pnpm", "build")')
    negative = literal_command_vectors('command = ["pnpm", "build"]')
    assert positive == (("corepack", "pnpm", "build"),)
    assert negative == (("pnpm", "build"),)
    assert command_executable(positive[0]) == (0, "corepack")
    assert command_executable(negative[0]) == (0, "pnpm")
    assert python_literal_pnpm_calls('subprocess.run("corepack pnpm build", shell=True)') == ()
    assert python_literal_pnpm_calls('subprocess.run("pnpm build", shell=True)') == ("pnpm build",)
    assert python_literal_pnpm_calls('subprocess.run(["bash", "-lc", "pnpm test"])') == (
        "pnpm test",
    )


def test_all_active_package_scripts_use_repository_pinned_pnpm() -> None:
    violations: list[str] = []
    for manifest in active_manifests():
        for name, command in sorted(manifest_document(manifest).get("scripts", {}).items()):
            for invocation in bare_shell_pnpm(command):
                violations.append(f"{manifest.relative_to(ROOT)}#{name}: {invocation}")
    assert not violations, "bare pnpm in production package scripts:\n" + "\n".join(violations)


def test_all_workflow_run_blocks_use_repository_pinned_pnpm() -> None:
    violations: list[str] = []
    for workflow, job, step, command in workflow_run_blocks():
        for invocation in bare_shell_pnpm(command):
            violations.append(f"{workflow.relative_to(ROOT)}:{job}:{step}: {invocation}")
    assert not violations, "bare pnpm in GitHub Actions run blocks:\n" + "\n".join(violations)


def test_production_nested_scripts_never_spawn_global_pnpm() -> None:
    violations: list[str] = []
    for path in production_script_sources():
        source = path.read_text(encoding="utf-8")
        if path.suffix == ".sh":
            for invocation in bare_shell_pnpm(source):
                violations.append(f"{path.relative_to(ROOT)}: {invocation}")
        elif path.suffix == ".py":
            for vector in literal_command_vectors(source):
                executable = command_executable(vector)
                if executable is not None and executable[1] == "pnpm":
                    violations.append(f"{path.relative_to(ROOT)}: {shlex.join(vector)}")
            for invocation in python_literal_pnpm_calls(source):
                violations.append(f"{path.relative_to(ROOT)}: {invocation}")
        elif JS_DIRECT_PNPM.search(source) or JS_SHELL_PNPM.search(source):
            violations.append(f"{path.relative_to(ROOT)}: direct pnpm child process")
    assert not violations, "bare pnpm in nested production scripts:\n" + "\n".join(violations)


def test_hosted_graph_reaches_nested_workflow_and_lifecycle_calls() -> None:
    packages, sources, edges = hosted_execution_graph()
    package_names = {(node.manifest.relative_to(ROOT).as_posix(), node.name) for node in packages}
    source_names = {path.relative_to(ROOT).as_posix() for path in sources}

    required_packages = {
        ("package.json", "audit:lock"),
        ("package.json", "audit:prod"),
        ("package.json", "build"),
        ("package.json", "presbom"),
        ("package.json", "sbom"),
        ("package.json", "test:compat"),
        ("apps/web/package.json", "build"),
        ("apps/web/package.json", "start"),
        ("apps/web/package.json", "test:compat"),
    }
    required_sources = {
        "scripts/ci/capture_runtime_evidence.py",
        "scripts/ci/rebuild_foundation.py",
        "scripts/ci/reproducible_foundation.sh",
        "scripts/generate-node-sbom.mjs",
        "scripts/prepare-sbom.mjs",
    }
    assert required_packages <= package_names
    assert required_sources <= source_names
    assert (
        "package.json#sbom",
        "package.json#presbom",
    ) in edges, "pnpm presbom lifecycle hook must be included in the hosted execution graph"


@pytest.mark.parametrize(
    "bad_command",
    [
        "pnpm --filter @visualization-agent/web build",
        "corepack pnpm test:compat && pnpm -r test:unit",
        "env CI=true pnpm audit --prod",
    ],
)
def test_negative_fixture_catches_nested_global_pnpm(bad_command: str) -> None:
    assert bare_shell_pnpm(bad_command)
