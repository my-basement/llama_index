"""PII postprocessor."""

from gpt_index.indices.postprocessor.node import BaseNodePostprocessor
from gpt_index.data_structs.node_v2 import Node
from typing import List, Optional, Dict, Tuple
from gpt_index.indices.service_context import ServiceContext
from gpt_index.prompts.prompts import QuestionAnswerPrompt
from copy import deepcopy
import json


DEFAULT_PII_TMPL = (
    "The current context information is provided. \n"
    "A task is also provided to mask the PII within the context. \n"
    "Return the text, with all PII masked out, and a mapping of the original PII "
    "to the masked PII. \n"
    "Return the output of the task in JSON. \n"
    "Context:\n"
    "Hello Zhang Wei, I am John. "
    "Your AnyCompany Financial Services, "
    "LLC credit card account 1111-0000-1111-0008 "
    "has a minimum payment of $24.53 that is due "
    "by July 31st. Based on your autopay settings, we will withdraw your payment. "
    "Task: Mask out the PII, replace each PII with a tag, and return the text. Return the mapping in JSON. \n"  # noqa: E501
    "Output: \n"
    "Hello [NAME1], I am [NAME2]. "
    "Your AnyCompany Financial Services, "
    "LLC credit card account [CREDIT_CARD_NUMBER] "
    "has a minimum payment of $24.53 that is due "
    "by [DATE_TIME]. Based on your autopay settings, we will withdraw your payment. "
    "Output Mapping:\n"
    '{{"NAME1": "Zhang Wei", "NAME2": "John", "CREDIT_CARD_NUMBER": "1111-0000-1111-0008", "DATE_TIME": "July 31st"}}\n'  # noqa: E501
    "Context:\n{context_str}\n"
    "Task: {query_str}\n"
    "Output: \n"
    ""
)


class PIINodePostprocessor(BaseNodePostprocessor):
    """PII Node processor.

    NOTE: this is a beta feature, the API might change.

    Args:
        service_context (ServiceContext): Service context.

    """

    service_context: ServiceContext
    pii_str_tmpl: str = DEFAULT_PII_TMPL
    pii_node_info_key: str = "__pii_node_info__"

    def mask_pii(self, text: str) -> Tuple[str, Dict]:
        """Mask PII in text."""
        pii_prompt = QuestionAnswerPrompt(self.pii_str_tmpl)
        # TODO: allow customization
        task_str = (
            "Mask out the PII, replace each PII with a tag, and return the text. "
            "Return the mapping in JSON."
        )

        response, _ = self.service_context.llm_predictor.predict(
            pii_prompt, context_str=text, query_str=task_str
        )
        splits = response.split("Output Mapping:")
        text_output = splits[0].strip()
        json_str_output = splits[1].strip()
        json_dict = json.loads(json_str_output)
        return text_output, json_dict

    def postprocess_nodes(
        self, nodes: List[Node], extra_info: Optional[Dict] = None
    ) -> List[Node]:
        """Postprocess nodes."""
        # swap out text from nodes, with the original node mappings
        new_nodes = []
        for node in nodes:
            new_text, mapping_info = self.mask_pii(node.get_text())
            new_node = deepcopy(node)
            new_node.node_info = new_node.node_info or {}
            new_node.node_info[self.pii_node_info_key] = mapping_info
            new_node.text = new_text
            new_nodes.append(new_node)

        return new_nodes
