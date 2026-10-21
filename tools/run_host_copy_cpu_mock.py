"""Compile and run a small CPU mock with an existing WSL g++ compiler only."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import time

parser = argparse.ArgumentParser()
parser.add_argument("--distribution", default="Ubuntu")
parser.add_argument("--compiler", default="/usr/bin/g++-14")
parser.add_argument("--build-name", default="host_copy_cpu_20261021")
parser.add_argument("--result", type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
out = root / "results/host_adapter_source_review_20261021"
build = root / "local_only" / args.build_name
build.mkdir(exist_ok=False)


def linux(path):
    value = path.resolve().as_posix()
    assert len(value) > 2 and value[1] == ":"
    return "/mnt/" + value[0].lower() + value[2:]


def run(argv):
    return subprocess.run(["wsl.exe", "--distribution", args.distribution, "--exec", *argv],
                          check=True, capture_output=True, text=True, timeout=60)


started = time.time()
compiler = run([args.compiler, "--version"]).stdout.splitlines()[0]
source = root / "tools/host_copy_cpu_mock.cpp"
binary = build / "host_copy_cpu_mock"
command = [args.compiler, "-std=c++17", "-O0", "-g", "-Wall", "-Wextra",
           "-fsanitize=address,undefined", "-I" + linux(out / "source_reference"), "-I" + linux(out),
           linux(source), "-o", linux(binary)]
try:
    compiled = run(command)
    execution = run([linux(binary)])
except subprocess.CalledProcessError as error:
    (build / "failure.stderr.local.txt").write_text(error.stderr or "", encoding="utf-8")
    raise RuntimeError("CPU mock failed; inspect the ignored local failure log") from None
result = json.loads(execution.stdout)
assert result["status"] == "CPU_ABI_AND_COPY_MOCK_PASS" and result["cases"] == 4
deps = run(["/usr/bin/ldd", linux(binary)]).stdout
assert "libcuda" not in deps and "libcudart" not in deps
result.update({"compiler": compiler, "distribution": args.distribution,
               "compile_flags": ["-std=c++17", "-O0", "-g", "-Wall", "-Wextra", "-fsanitize=address,undefined"],
               "source_path": source.relative_to(root).as_posix(),
               "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
               "compiled_copy_function_sha256": hashlib.sha256((out / "copyInResults.inc").read_bytes()).hexdigest(),
               "ELF_binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
               "compile_and_run_elapsed_s": time.time() - started,
               "sanitizer_scope": "CPU object access in this mock only; no CUDA device or native race-freedom validation",
               "CPU_compile_warnings": bool(compiled.stderr.strip()),
               "mock_runtime_stderr_empty": not execution.stderr.strip(),
               "CUDA_runtime_libraries_linked": False,
               "mock_CUDA_annotations": "Header host-guard branch selected using empty annotations; this is a g++ CPU program, not nvcc.",
               "native_alignment_or_GPU_run": False})
result_path = args.result.resolve() if args.result else out / "abi_and_copy_cpu_mock.json"
if args.result:
    assert not result_path.exists(), "Choose a fresh result path"
result_path.parent.mkdir(parents=True, exist_ok=True)
result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
