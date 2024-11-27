import os
import logging
from dotenv import load_dotenv

from graphrag_sdk.models.openai import OpenAiGenerativeModel
#from graphrag_sdk.models.gemini import GeminiGenerativeModel
from prompts import (CYPHER_GEN_SYSTEM,
                     CYPHER_GEN_PROMPT,
                     GRAPH_QA_SYSTEM,
                     GRAPH_QA_PROMPT,
                    )
from graphrag_sdk import (
    Ontology,
    Entity,
    Relation,
    Attribute,
    AttributeType,
    KnowledgeGraph,
    KnowledgeGraphModelConfig
)
load_dotenv()

def define_ontology():
    ontology = Ontology()

    function = Entity(
            label="Function",
            attributes=[
                Attribute(
                    name="name",
                    attr_type=AttributeType.STRING,
                    required=True,
                    unique=True,
                ),
                Attribute(
                    name="path",
                    attr_type=AttributeType.STRING,
                    required=False,
                    unique=False,
                ),
                Attribute(
                    name="src_start",
                    attr_type=AttributeType.NUMBER,
                    required=False,
                    unique=False,
                ),
                Attribute(
                    name="src_end",
                    attr_type=AttributeType.NUMBER,
                    required=False,
                    unique=False,
                ),
                Attribute(
                    name="args",
                    attr_type=AttributeType.STRING,
                    required=False,
                    unique=False,
                ),
                Attribute(
                    name="src",
                    attr_type=AttributeType.STRING,
                    required=False,
                    unique=False,
                ),
            ]
        )


    file = Entity(
            label="File",
            attributes=[
                    Attribute(
                    name="name",
                    attr_type=AttributeType.STRING,
                    required=True,
                    unique=True,
                ),
                    Attribute(
                        name="path",
                        attr_type=AttributeType.STRING,
                        required=False,
                        unique=False,
                    ),
                    Attribute(
                        name="ext",
                        attr_type=AttributeType.STRING,
                        required=False,
                        unique=False,
                    )
            ]
        )

    cls = Entity(
            label="Class",
            attributes=[
                Attribute(
                    name="name",
                    attr_type=AttributeType.STRING,
                    required=True,
                    unique=True,
                ),
                Attribute(
                    name="path",
                    attr_type=AttributeType.STRING,
                    required=False,
                    unique=False,
                ),
                Attribute(
                    name="src_start",
                    attr_type=AttributeType.NUMBER,
                    required=False,
                    unique=False,
                ),
                Attribute(
                    name="src_end",
                    attr_type=AttributeType.NUMBER,
                    required=False,
                    unique=False,
                ),
                Attribute(
                    name="doc",
                    attr_type=AttributeType.STRING,
                    required=False,
                    unique=False,
                ),
            ]
        )

    ontology.add_entity(cls)
    ontology.add_entity(file)
    ontology.add_entity(function)

    ontology.add_relation(Relation("CALLS",   "Class",    "Function"))
    ontology.add_relation(Relation("CALLS",   "Function", "Function"))
    ontology.add_relation(Relation("DEFINES", "File",     "Class"))
    ontology.add_relation(Relation("DEFINES", "File",     "Function"))
    ontology.add_relation(Relation("DEFINES", "Class",    "Class"))
    ontology.add_relation(Relation("DEFINES", "Class",    "Function"))
    ontology.add_relation(Relation("DEFINES", "Function", "Function"))

    return ontology
def main():
    
    repo_name = "GraphRAG-SDK"
    
    ontology = define_ontology()
    openapi_model    = OpenAiGenerativeModel("gpt-4o")
    #gemini_model     = GeminiGenerativeModel("gemini-1.5-flash-001")
    #gemini_model_pro = GeminiGenerativeModel("gemini-1.5-pro")

    code_graph_kg = KnowledgeGraph(
        name=repo_name,
        ontology=ontology,
        model_config=KnowledgeGraphModelConfig.with_model(openapi_model),
        host=os.getenv('FALKORDB_HOST', 'localhost'),
        port=os.getenv('FALKORDB_PORT', 6379),
        username=os.getenv('FALKORDB_USERNAME', None),
        password=os.getenv('FALKORDB_PASSWORD', None),
        cypher_system_instruction=CYPHER_GEN_SYSTEM,
        qa_system_instruction=GRAPH_QA_SYSTEM,
        cypher_gen_prompt=CYPHER_GEN_PROMPT,
        qa_prompt=GRAPH_QA_PROMPT,
    )
    
    qs = [
        "List a few recursive functions",
          "What is the name of the most used method?",
          "Who is calling the most used method?",
          "Which function has the largest number of arguments? List a few arguments",
          "Show a calling path between 2 functions in the graph, only return function(s) names"
        ]
    for q in qs:
        chat = code_graph_kg.chat_session()
        response = chat.send_message(q)
        print("Q: " + response['question']+ "\n")
        print("Cypher: " + response['cypher'])
        print("A: " + response['response']+"\n")
    
if __name__ == "__main__":
    main()