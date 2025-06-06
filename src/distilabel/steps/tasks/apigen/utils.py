# Copyright 2023-present, Argilla, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import importlib.util
import re
import signal
from typing import TYPE_CHECKING, Any, Callable, Dict, TypedDict, Union

from distilabel.steps.base import Step, StepInput

if TYPE_CHECKING:
    from types import ModuleType

    from distilabel.typing import StepColumns, StepOutput


class PrepareExamples(Step):
    r"""Helper step to create examples from `query` and `answers` pairs used as Few Shots in APIGen.

    Attributes:
        template (str): The template to format the examples.

    Input columns:
        - query (`str`): The query to generate examples from.
        - answers (`str`): The answers to the query.

    Output columns:
        - examples (`str`): The formatted examples.

    Categories:
        - format

    Examples:
        Generate examples for APIGen:

        ```python
        from distilabel.steps.tasks.apigen.utils import PrepareExamples

        prepare_examples = PrepareExamples()
        result = next(prepare_examples.process(
            [
                {
                    "query": ['I need the area of circles with radius 2.5, 5, and 7.5 inches, please.', 'Can you provide the current locations of buses and trolleys on route 12?'],
                    "answers": ['[{"name": "circle_area", "arguments": {"radius": 2.5}}, {"name": "circle_area", "arguments": {"radius": 5}}, {"name": "circle_area", "arguments": {"radius": 7.5}}]', '[{"name": "bus_trolley_locations", "arguments": {"route": "12"}}]']
                }
            ]
        )
        # result
        # [{'examples': '## Query:\nI need the area of circles with radius 2.5, 5, and 7.5 inches, please.\n## Answers:\n[{"name": "circle_area", "arguments": {"radius": 2.5}}, {"name": "circle_area", "arguments": {"radius": 5}}, {"name": "circle_area", "arguments": {"radius": 7.5}}]\n\n## Query:\nCan you provide the current locations of buses and trolleys on route 12?\n## Answers:\n[{"name": "bus_trolley_locations", "arguments": {"route": "12"}}]'}, {'examples': '## Query:\nI need the area of circles with radius 2.5, 5, and 7.5 inches, please.\n## Answers:\n[{"name": "circle_area", "arguments": {"radius": 2.5}}, {"name": "circle_area", "arguments": {"radius": 5}}, {"name": "circle_area", "arguments": {"radius": 7.5}}]\n\n## Query:\nCan you provide the current locations of buses and trolleys on route 12?\n## Answers:\n[{"name": "bus_trolley_locations", "arguments": {"route": "12"}}]'}]
        ```
    """

    template: str = "## Query:\n{query}\n## Answers:\n{answers}"

    @property
    def inputs(self) -> "StepColumns":
        return ["query", "answers"]

    @property
    def outputs(self) -> "StepColumns":
        return ["examples"]

    def process(self, inputs: StepInput) -> "StepOutput":
        """The process prepares the data for the `APIGenGenerator` task.

        If a single example is provided, it is copied to avoid raising an error.

        Args:
            inputs: A list of dictionaries with the input data.

        Yields:
            A list of dictionaries with the output data.
        """
        outputs = []
        for input in inputs:
            example_list = []
            for query, answers in zip(input["query"], input["answers"]):
                example_list.append(self.template.format(query=query, answers=answers))
            outputs.append({"examples": "\n\n".join(example_list)})

        yield outputs


def load_module_from_path(path: str) -> "ModuleType":
    """Loads a python module from a given path.

    Args:
        path: Path pointing to the module.

    Returns:
        ModuleType

    Example:
        ```python
        path = "/path/to/module.py"
        module = load_module_from_path(path)
        # And you can load functions from the module like this:
        function = getattr(module, "function_name")
        function(*args, **kwargs)
        ```
    """
    spec = importlib.util.spec_from_file_location("module.name", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FunctionResult(TypedDict):
    keep: bool
    execution_result: str


def execute_from_response(
    function: Callable, call_answer: Union[Dict[str, Any], None]
) -> FunctionResult:
    """Executes a function with the given arguments as generated by `APIGenGenerator`.

    Given that we cannot cast all the arguments arbitrarily, we try to evaluate them,
    which ensures the strings can be converted to the correct type if possible (say
    a list of lists of ints will be passed as such instead of its string representation).

    Args:
        function: A callable object.
        call_answer: The arguments to call the function, as generated by the model.

    Returns:
        A container with the result of the execution and if the row should be kept.
    """
    if not function:
        return FunctionResult(keep=False, execution_result="Function not found")

    if call_answer:
        for key, value in call_answer.items():
            if isinstance(value, str):
                try:
                    call_answer[key] = eval(value)
                except Exception:
                    # Leave as is and expect the function to handle it
                    pass

    try:
        if call_answer:
            result = run_function_with_timeout(function, 5, *call_answer.values())
        else:
            # There can be functions that do not require arguments
            result = run_function_with_timeout(function, 5)
        return FunctionResult(keep=True, execution_result=str(result))
    except Exception as e:
        return FunctionResult(keep=False, execution_result=str(e))


def remove_json_fences(text: str) -> str:
    pattern = r"^```json\n([\s\S]*)\n```$"
    match = re.match(pattern, text, re.MULTILINE)
    if match:
        return match.group(1)
    return text


def remove_fences(text: str) -> str:
    pattern = r"^```\n([\s\S]*)\n```$"
    match = re.match(pattern, text, re.MULTILINE)
    if match:
        return match.group(1)
    return text


def timeout_handler(signum, frame):
    raise TimeoutError("Function execution timed out")


def run_function_with_timeout(function: Callable, timeout: int = 5, *args: Any) -> Any:
    """Run a function with a timeout, to limit the total time waiting for a result."""
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout)

    try:
        result = function(*args)
    finally:
        # Cancel the alarm
        signal.alarm(0)

    return result
