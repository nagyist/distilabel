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

import hashlib
from typing import TYPE_CHECKING, List

from pydantic import Field

from distilabel.steps.base import Step, StepInput

if TYPE_CHECKING:
    from distilabel.steps.typing import StepColumns, StepOutput


class FormatTextGenerationSFT(Step):
    r"""Format the output of a `TextGeneration` task for Supervised Fine-Tuning (SFT).

    `FormatTextGenerationSFT` is a `Step` that formats the output of a `TextGeneration` task for
    Supervised Fine-Tuning (SFT) following the standard formatting from frameworks such as `axolotl`
    or `alignment-handbook`. The output of the `TextGeneration` task is formatted into a chat-like
    conversation with the `instruction` as the user message and the `generation` as the assistant
    message. Optionally, if the `system_prompt` is available, it is included as the first message
    in the conversation.

    Attributes:
        tools (bool): If `tools` are available, they are included in the formatted output.

    Input columns:
        - system_prompt (`str`, optional): The system prompt used within the `LLM` to generate the
            `generation`, if available.
        - instruction (`str`): The instruction used to generate the `generation` with the `LLM`.
        - generation (`str`): The generation produced by the `LLM`.
        - tools (`str`, optional): If `tools` columns is available and is `tools=True`, this field
            will be used to prepare the dataset for fine-tuning with function calling.

    Output columns:
        - prompt (`str`): The instruction used to generate the `generation` with the `LLM`.
        - prompt_id (`str`): The `SHA256` hash of the `prompt`.
        - messages (`List[Dict[str, str]]`): The chat-like conversation with the `instruction` as
            the user message and the `generation` as the assistant message.

    Categories:
        - format
        - text-generation
        - instruction
        - generation

    Examples:
        Format your dataset for SFT fine tuning:

        ```python
        from distilabel.steps import FormatTextGenerationSFT

        format_sft = FormatTextGenerationSFT()
        format_sft.load()

        # NOTE: "system_prompt" can be added optionally.
        result = next(
            format_sft.process(
                [
                    {
                        "instruction": "What's 2+2?",
                        "generation": "4"
                    }
                ]
            )
        )
        # >>> result
        # [
        #     {
        #         'instruction': 'What's 2+2?',
        #         'generation': '4',
        #         'prompt': 'What's 2+2?',
        #         'prompt_id': '7762ecf17ad41479767061a8f4a7bfa3b63d371672af5180872f9b82b4cd4e29',
        #         'messages': [{'role': 'user', 'content': "What's 2+2?"}, {'role': 'assistant', 'content': '4'}]
        #     }
        # ]
        ```

        Format your dataset for SFT fine tuning with with function-calling:

        ```python
        from distilabel.steps import FormatTextGenerationSFT

        format_sft = FormatTextGenerationSFT(tools=True)
        format_sft.load()

        # NOTE: "system_prompt" can be added optionally.
        result = next(
            format_sft.process(
                [
                    {
                        "instruction": "I'd like to convert the complex number 3 + 4j and 1 - 2j to polar coordinates.",
                        "generation": "[{\"name\": \"complex_to_polar\", \"arguments\": {\"complex_number\": \"3 + 4j\"}}, {\"name\": \"complex_to_polar\", \"arguments\": {\"complex_number\": \"1 - 2j\"}}]",
                        "tools": "[{\"type\":\"function\",\"function\":{\"name\":\"complex_to_polar\",\"description\":\"Converts a complex number to its polar coordinate representation.\",\"parameters\":{\"type\":\"object\",\"properties\":{\"complex_number\":{\"type\":\"object\",\"description\":\"A complex number in the form of `real + imaginary * 1j`.\"}},\"required\":[\"complex_number\"]}}}]",
                    }
                ]
            )
        )
    """

    tools: bool = Field(
        default=False,
        description="If `tools` are available, they are included in the formatted output.",
    )

    @property
    def inputs(self) -> "StepColumns":
        """List of inputs required by the `Step`, which in this case are: `instruction`, and `generation`."""
        return {
            "system_prompt": False,
            "instruction": True,
            "generation": True,
            "tools": False,
        }

    @property
    def optional_inputs(self) -> List[str]:
        """List of optional inputs, which are not required by the `Step` but used if available,
        which in this case is: `system_prompt`."""
        return ["system_prompt"]

    @property
    def outputs(self) -> "StepColumns":
        """List of outputs generated by the `Step`, which are: `prompt`, `prompt_id`, `messages`.

        Reference:
            - Format inspired in https://huggingface.co/datasets/HuggingFaceH4/ultrachat_200k
        """
        return ["prompt", "prompt_id", "messages"]

    def process(self, *inputs: StepInput) -> "StepOutput":  # type: ignore
        """The `process` method formats the received `StepInput` or list of `StepInput`
        according to the SFT formatting standard.

        Args:
            *inputs: A list of `StepInput` to be combined.

        Yields:
            A `StepOutput` with batches of formatted `StepInput` following the SFT standard.
        """
        for input in inputs:
            for item in input:
                item["prompt"] = item["instruction"]

                item["prompt_id"] = hashlib.sha256(
                    item["prompt"].encode("utf-8")  # type: ignore
                ).hexdigest()

                item["messages"] = [
                    {"role": "user", "content": item["instruction"]},  # type: ignore
                ]
                if not self.tools:
                    item["messages"].append(
                        {"role": "assistant", "content": item["generation"]}
                    )
                else:
                    item["messages"].append(
                        {"role": "assistant", "tool_calls": item["generation"]}
                    )
                    item["messages"].append({"role": "tool", "content": item["tools"]})

                if (
                    "system_prompt" in item
                    and isinstance(item["system_prompt"], str)  # type: ignore
                    and len(item["system_prompt"]) > 0  # type: ignore
                ):
                    item["messages"].insert(
                        0,
                        {"role": "system", "content": item["system_prompt"]},  # type: ignore
                    )

            yield input


class FormatChatGenerationSFT(Step):
    """Format the output of a `ChatGeneration` task for Supervised Fine-Tuning (SFT).

    `FormatChatGenerationSFT` is a `Step` that formats the output of a `ChatGeneration` task for
    Supervised Fine-Tuning (SFT) following the standard formatting from frameworks such as `axolotl`
    or `alignment-handbook`. The output of the `ChatGeneration` task is formatted into a chat-like
    conversation with the `instruction` as the user message and the `generation` as the assistant
    message. Optionally, if the `system_prompt` is available, it is included as the first message
    in the conversation.

    Input columns:
        - system_prompt (`str`, optional): The system prompt used within the `LLM` to generate the
            `generation`, if available.
        - instruction (`str`): The instruction used to generate the `generation` with the `LLM`.
        - generation (`str`): The generation produced by the `LLM`.

    Output columns:
        - prompt (`str`): The instruction used to generate the `generation` with the `LLM`.
        - prompt_id (`str`): The `SHA256` hash of the `prompt`.
        - messages (`List[Dict[str, str]]`): The chat-like conversation with the `instruction` as
            the user message and the `generation` as the assistant message.

    Categories:
        - format
        - chat-generation
        - instruction
        - generation

    Examples:
        Format your dataset for SFT:

        ```python
        from distilabel.steps import FormatChatGenerationSFT

        format_sft = FormatChatGenerationSFT()
        format_sft.load()

        # NOTE: "system_prompt" can be added optionally.
        result = next(
            format_sft.process(
                [
                    {
                        "messages": [{"role": "user", "content": "What's 2+2?"}],
                        "generation": "4"
                    }
                ]
            )
        )
        # >>> result
        # [
        #     {
        #         'messages': [{'role': 'user', 'content': "What's 2+2?"}, {'role': 'assistant', 'content': '4'}],
        #         'generation': '4',
        #         'prompt': 'What's 2+2?',
        #         'prompt_id': '7762ecf17ad41479767061a8f4a7bfa3b63d371672af5180872f9b82b4cd4e29',
        #     }
        # ]
        ```
    """

    @property
    def inputs(self) -> "StepColumns":
        """List of inputs required by the `Step`, which in this case are: `instruction`, and `generation`."""
        return ["messages", "generation"]

    @property
    def outputs(self) -> "StepColumns":
        """List of outputs generated by the `Step`, which are: `prompt`, `prompt_id`, `messages`.

        Reference:
            - Format inspired in https://huggingface.co/datasets/HuggingFaceH4/ultrachat_200k
        """
        return ["prompt", "prompt_id", "messages"]

    def process(self, *inputs: StepInput) -> "StepOutput":  # type: ignore
        """The `process` method formats the received `StepInput` or list of `StepInput`
        according to the SFT formatting standard.

        Args:
            *inputs: A list of `StepInput` to be combined.

        Yields:
            A `StepOutput` with batches of formatted `StepInput` following the SFT standard.
        """
        for input in inputs:
            for item in input:
                item["prompt"] = next(
                    (
                        turn["content"]
                        for turn in item["messages"]
                        if turn["role"] == "user"
                    ),
                    None,
                )

                item["prompt_id"] = hashlib.sha256(
                    item["prompt"].encode("utf-8")  # type: ignore
                ).hexdigest()

                item["messages"] = item["messages"] + [
                    {"role": "assistant", "content": item["generation"]},  # type: ignore
                ]
            yield input
