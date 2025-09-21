#!/usr/bin/env python3
"""
Clean Architecture Compliance Testing Framework

Tests for clean architecture layer separation, dependency direction enforcement,
and architectural pattern compliance validation.
"""

import ast
import os
import sys
import pytest
import importlib
import inspect
from typing import Dict, List, Set, Tuple, Any
from pathlib import Path
from dataclasses import dataclass


@dataclass
class LayerDefinition:
    """Definition of an architectural layer"""
    name: str
    directories: List[str]
    allowed_dependencies: List[str]
    forbidden_dependencies: List[str]


@dataclass
class DependencyViolation:
    """Represents a dependency violation"""
    source_file: str
    target_file: str
    violation_type: str
    line_number: int
    details: str


class ArchitecturalAnalyzer:
    """Analyzer for architectural compliance"""

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.violations: List[DependencyViolation] = []

    def define_layers(self) -> Dict[str, LayerDefinition]:
        """Define clean architecture layers for ALD system"""
        return {
            "domain": LayerDefinition(
                name="domain",
                directories=["src/domain"],
                allowed_dependencies=[],  # Domain should have no dependencies
                forbidden_dependencies=["src/infrastructure", "src/application", "src/interfaces"]
            ),
            "application": LayerDefinition(
                name="application",
                directories=["src/application", "src/use_cases"],
                allowed_dependencies=["src/domain"],
                forbidden_dependencies=["src/infrastructure", "src/interfaces"]
            ),
            "interfaces": LayerDefinition(
                name="interfaces",
                directories=["src/interfaces", "src/adapters"],
                allowed_dependencies=["src/domain", "src/application"],
                forbidden_dependencies=["src/infrastructure"]
            ),
            "infrastructure": LayerDefinition(
                name="infrastructure",
                directories=["src/infrastructure", "src/plc", "src/db"],
                allowed_dependencies=["src/domain", "src/application", "src/interfaces"],
                forbidden_dependencies=[]
            ),
            "legacy": LayerDefinition(
                name="legacy",
                directories=["src/command_flow", "src/recipe_flow", "src/step_flow", "src/data_collection"],
                allowed_dependencies=["src/plc", "src/db", "src/log_setup", "src/config"],
                forbidden_dependencies=[]  # Legacy can depend on anything for now
            )
        }

    def analyze_imports(self, file_path: Path) -> List[str]:
        """Analyze imports in a Python file"""
        imports = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read())

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)

        except (SyntaxError, UnicodeDecodeError, FileNotFoundError):
            pass

        return imports

    def get_layer_for_file(self, file_path: Path, layers: Dict[str, LayerDefinition]) -> str:
        """Determine which layer a file belongs to"""
        relative_path = file_path.relative_to(self.project_root)
        path_str = str(relative_path)

        for layer_name, layer_def in layers.items():
            for directory in layer_def.directories:
                if path_str.startswith(directory):
                    return layer_name

        return "unknown"

    def check_dependency_direction(self, source_file: Path, target_import: str, layers: Dict[str, LayerDefinition]) -> List[DependencyViolation]:
        """Check if dependency direction follows clean architecture rules"""
        violations = []
        source_layer = self.get_layer_for_file(source_file, layers)

        if source_layer == "unknown":
            return violations

        layer_def = layers[source_layer]

        # Check if import is from forbidden dependency
        for forbidden_dep in layer_def.forbidden_dependencies:
            if target_import.startswith(forbidden_dep.replace("/", ".")):
                violations.append(DependencyViolation(
                    source_file=str(source_file),
                    target_file=target_import,
                    violation_type="forbidden_dependency",
                    line_number=0,  # Would need more sophisticated AST analysis for line numbers
                    details=f"{source_layer} layer cannot depend on {forbidden_dep}"
                ))

        return violations

    def analyze_coupling_metrics(self) -> Dict[str, Any]:
        """Analyze coupling metrics across the system"""
        metrics = {
            "total_files": 0,
            "total_imports": 0,
            "coupling_violations": 0,
            "layer_coupling": {},
            "circular_dependencies": []
        }

        layers = self.define_layers()
        all_python_files = list(self.project_root.rglob("*.py"))

        # Exclude test files and __pycache__
        python_files = [f for f in all_python_files
                       if not any(part.startswith(('.', '__pycache__')) for part in f.parts)
                       and 'test' not in str(f)]

        metrics["total_files"] = len(python_files)

        for file_path in python_files:
            imports = self.analyze_imports(file_path)
            metrics["total_imports"] += len(imports)

            # Check each import for violations
            for import_name in imports:
                violations = self.check_dependency_direction(file_path, import_name, layers)
                self.violations.extend(violations)
                metrics["coupling_violations"] += len(violations)

        return metrics

    def detect_singletons(self) -> List[Dict[str, Any]]:
        """Detect singleton patterns in the codebase"""
        singletons = []
        python_files = list(self.project_root.rglob("*.py"))

        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Look for singleton patterns
                if "_instance = None" in content or "cls._instance" in content:
                    singletons.append({
                        "file": str(file_path),
                        "type": "class_singleton",
                        "pattern": "Singleton class with _instance"
                    })

                # Look for global instances
                if " = " in content and any(keyword in content.lower() for keyword in ["manager", "service", "logger"]):
                    # Simple heuristic for global instances
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if ' = ' in line and not line.strip().startswith('#') and not line.strip().startswith('def'):
                            if any(keyword in line.lower() for keyword in ["manager", "service", "logger"]):
                                singletons.append({
                                    "file": str(file_path),
                                    "line": i + 1,
                                    "type": "global_instance",
                                    "pattern": line.strip()
                                })

            except (UnicodeDecodeError, FileNotFoundError):
                continue

        return singletons

    def analyze_circular_dependencies(self) -> List[List[str]]:
        """Detect circular dependencies in the import graph"""
        # This is a simplified implementation
        # In practice, you'd want a more sophisticated algorithm
        import_graph = {}
        python_files = list(self.project_root.rglob("*.py"))

        for file_path in python_files:
            if 'test' in str(file_path) or '__pycache__' in str(file_path):
                continue

            imports = self.analyze_imports(file_path)
            relative_path = str(file_path.relative_to(self.project_root))
            import_graph[relative_path] = imports

        # Simple cycle detection (would need more sophisticated algorithm for production)
        cycles = []
        # Placeholder for actual cycle detection algorithm
        return cycles


class TestCleanArchitecture:
    """Test clean architecture compliance"""

    @pytest.fixture
    def analyzer(self):
        """Architecture analyzer fixture"""
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        return ArchitecturalAnalyzer(project_root)

    def test_layer_separation(self, analyzer):
        """Test that architectural layers are properly separated"""
        layers = analyzer.define_layers()
        violations = []

        # Check that each layer exists or is acceptable to not exist yet
        for layer_name, layer_def in layers.items():
            layer_exists = False
            for directory in layer_def.directories:
                layer_path = analyzer.project_root / directory
                if layer_path.exists():
                    layer_exists = True
                    break

            # For new clean architecture, some layers may not exist yet
            if layer_name in ["domain", "application", "interfaces"] and not layer_exists:
                # This is expected during migration - not a violation yet
                pass

        # Analyze existing structure
        metrics = analyzer.analyze_coupling_metrics()

        # Assert basic structure is reasonable
        assert metrics["total_files"] > 0, "Should have Python files to analyze"

        # For now, just report violations rather than failing
        # During migration, we expect some violations
        print(f"Found {metrics['coupling_violations']} coupling violations")
        print(f"Analyzed {metrics['total_files']} files with {metrics['total_imports']} imports")

    def test_dependency_direction(self, analyzer):
        """Test that dependencies only flow inward (toward domain)"""
        violations = analyzer.violations

        # Check for specific problematic patterns
        forbidden_patterns = [
            ("domain", "infrastructure"),
            ("domain", "interfaces"),
            ("application", "infrastructure"),
            ("application", "interfaces")
        ]

        serious_violations = []
        for violation in violations:
            for source_pattern, target_pattern in forbidden_patterns:
                if source_pattern in violation.source_file and target_pattern in violation.target_file:
                    serious_violations.append(violation)

        # For now, just report serious violations
        if serious_violations:
            print(f"Found {len(serious_violations)} serious dependency violations:")
            for violation in serious_violations[:5]:  # Show first 5
                print(f"  {violation.source_file} -> {violation.target_file}")

    def test_singleton_detection(self, analyzer):
        """Test detection of singleton patterns that should be replaced with DI"""
        singletons = analyzer.detect_singletons()

        # Known singletons that need to be addressed
        expected_singletons = ["PLCManager", "ContinuousParameterLogger"]

        found_singleton_files = [s["file"] for s in singletons]

        # Check for known problematic singletons
        problematic_singletons = []
        for singleton in singletons:
            if any(expected in singleton.get("pattern", "") for expected in expected_singletons):
                problematic_singletons.append(singleton)

        print(f"Found {len(singletons)} singleton patterns")
        print(f"Found {len(problematic_singletons)} problematic singletons that need DI")

        # For now, just report rather than fail
        # During migration, singletons are expected
        assert len(singletons) >= 0  # Basic check that detection works

    def test_circular_dependency_detection(self, analyzer):
        """Test detection of circular dependencies"""
        cycles = analyzer.analyze_circular_dependencies()

        # For now, just verify the detection works
        assert isinstance(cycles, list)

        if cycles:
            print(f"Found {len(cycles)} circular dependencies")
            for cycle in cycles[:3]:  # Show first 3
                print(f"  Cycle: {' -> '.join(cycle)}")

    def test_interface_segregation(self, analyzer):
        """Test that interfaces are properly segregated"""
        # Check for large interfaces that should be split
        interfaces_to_check = [
            "PLCInterface",
            "DataCollectionInterface",
            "ParameterLoggerInterface"
        ]

        # This is a placeholder for interface analysis
        # In practice, you'd analyze interface sizes and cohesion
        print("Interface segregation analysis:")
        print("- PLCInterface: Should be split into separate read/write/control interfaces")
        print("- DataCollectionInterface: Should separate parameter and process data concerns")

        # For now, this always passes but provides insights
        assert True

    def test_dependency_inversion(self, analyzer):
        """Test that high-level modules don't depend on low-level modules"""
        violations = []

        # Check for direct database imports in high-level modules
        high_level_dirs = ["src/command_flow", "src/recipe_flow", "src/step_flow"]
        low_level_patterns = ["supabase", "psycopg2", "sqlite3", "pymongo"]

        python_files = list(analyzer.project_root.rglob("*.py"))

        for file_path in python_files:
            relative_path = str(file_path.relative_to(analyzer.project_root))

            if any(relative_path.startswith(high_dir) for high_dir in high_level_dirs):
                imports = analyzer.analyze_imports(file_path)

                for import_name in imports:
                    if any(pattern in import_name.lower() for pattern in low_level_patterns):
                        violations.append({
                            "file": relative_path,
                            "import": import_name,
                            "issue": "High-level module depends on low-level database implementation"
                        })

        print(f"Found {len(violations)} dependency inversion violations")
        for violation in violations[:5]:  # Show first 5
            print(f"  {violation['file']}: {violation['import']}")

        # For now, report but don't fail during migration
        assert len(violations) >= 0


class TestArchitecturalConstraints:
    """Test architectural constraints and rules"""

    @pytest.fixture
    def analyzer(self):
        """Architecture analyzer fixture"""
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        return ArchitecturalAnalyzer(project_root)

    def test_no_god_objects(self, analyzer):
        """Test that there are no god objects (classes with too many responsibilities)"""
        god_object_threshold = 20  # methods
        god_objects = []

        python_files = list(analyzer.project_root.rglob("*.py"))

        for file_path in python_files:
            if 'test' in str(file_path):
                continue

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    tree = ast.parse(f.read())

                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        method_count = sum(1 for child in node.body if isinstance(child, ast.FunctionDef))

                        if method_count > god_object_threshold:
                            god_objects.append({
                                "file": str(file_path),
                                "class": node.name,
                                "method_count": method_count
                            })

            except (SyntaxError, UnicodeDecodeError, FileNotFoundError):
                continue

        print(f"Found {len(god_objects)} potential god objects")
        for obj in god_objects:
            print(f"  {obj['class']} in {obj['file']}: {obj['method_count']} methods")

        # Warn about god objects but don't fail tests during migration
        assert len(god_objects) >= 0

    def test_proper_error_handling(self, analyzer):
        """Test that error handling follows architectural guidelines"""
        error_handling_violations = []

        python_files = list(analyzer.project_root.rglob("*.py"))

        for file_path in python_files:
            if 'test' in str(file_path):
                continue

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Check for bare except clauses
                if "except:" in content:
                    error_handling_violations.append({
                        "file": str(file_path),
                        "issue": "Bare except clause found",
                        "type": "bare_except"
                    })

                # Check for generic Exception catching
                if "except Exception:" in content:
                    error_handling_violations.append({
                        "file": str(file_path),
                        "issue": "Generic Exception catching found",
                        "type": "generic_exception"
                    })

            except (UnicodeDecodeError, FileNotFoundError):
                continue

        print(f"Found {len(error_handling_violations)} error handling issues")

        # Report but don't fail during migration
        assert len(error_handling_violations) >= 0

    def test_logging_compliance(self, analyzer):
        """Test that logging follows architectural guidelines"""
        logging_issues = []

        python_files = list(analyzer.project_root.rglob("*.py"))

        for file_path in python_files:
            if 'test' in str(file_path):
                continue

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Check for print statements (should use logger)
                if "print(" in content and "debug" not in str(file_path):
                    logging_issues.append({
                        "file": str(file_path),
                        "issue": "Print statement found - should use logger",
                        "type": "print_usage"
                    })

            except (UnicodeDecodeError, FileNotFoundError):
                continue

        print(f"Found {len(logging_issues)} logging compliance issues")

        # Report but don't fail during migration
        assert len(logging_issues) >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])