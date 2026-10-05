# MedRAG End-to-End Application Workflow

This diagram follows a user question through the application to the final answer, including current validation, authentication, guardrail, and error behavior.

## User question to final response

```mermaid
flowchart LR
    user([User])

    subgraph frontend[Frontend: Streamlit]
        ui[Question form]
        blank{Question blank?}
        ui_error[Show "Enter a question first"]
        show_result[Render answer, evidence, sources, confidence, disclaimer]
        show_error[Render API error]
    end

    subgraph backend[Backend/API: FastAPI]
        endpoint[POST /query]
        auth_status[Authentication<br/>Not configured; request proceeds]
        schema{Pydantic validation<br/>question length >= 5?}
        validation_error[Return HTTP 422]
        input_check{Input guardrail allows?}
        input_block[Return HTTP 422<br/>prompt injection blocked]
        service_call[RAGService.query<br/>runs under service lock]
        ready{Qdrant collection ready?}
        missing_index[Return HTTP 503<br/>index missing]
        query_error[Return HTTP 500<br/>unexpected query error]
        output_check{Output safeguard allows?}
        output_block[Return HTTP 422<br/>policy violation]
        response[Return RAGResponse JSON]
    end

    subgraph logic[Business Logic]
        load_index[Load cached vector index if needed]
        make_query[Build query engine and retrieve context]
        compose[Package answer, evidence, sources,<br/>confidence, and disclaimer]
    end

    subgraph models[AI / LLM]
        embed[FastEmbed<br/>local query embedding]
        llm[OpenAI LLM<br/>draft answer from retrieved context]
    end

    subgraph database[Database]
        qdrant[(Qdrant vector collection<br/>guideline chunks and vectors)]
    end

    subgraph external[External service: Groq, when GROQ_API_KEY is set]
        prompt_guard[Prompt Guard<br/>input risk score]
        safeguard[Safeguard model<br/>output policy verdict]
    end

    user --> ui --> blank
    blank -- Yes --> ui_error --> user
    blank -- No -->|POST question as JSON| endpoint
    endpoint --> auth_status --> schema
    schema -- No --> validation_error --> show_error
    schema -- Yes --> input_check

    input_check -. configured .-> prompt_guard
    prompt_guard -- score at/above threshold --> input_block --> show_error
    prompt_guard -- below threshold --> service_call
    input_check -- Groq key absent or call fails: fail open --> service_call

    service_call --> ready
    ready -- No --> missing_index --> show_error
    ready -- Yes --> load_index --> make_query
    make_query --> embed
    embed -->|query vector| qdrant
    qdrant -->|top matching passages| make_query
    make_query -->|question + retrieved context| llm
    llm -->|generated answer| compose
    compose --> output_check

    output_check -. configured .-> safeguard
    safeguard -- Violation --> output_block --> show_error
    safeguard -- Allowed --> response
    output_check -- Groq key absent or call fails: fail open --> response
    response --> show_result --> user

    service_call -. unhandled retrieval or LLM error .-> query_error --> show_error
    make_query -. retrieval error .-> query_error
    llm -. generation error .-> query_error
    show_error --> user

    classDef decision fill:#fff3cd,stroke:#9a6700,color:#24292f;
    classDef error fill:#ffebe9,stroke:#cf222e,color:#24292f;
    classDef externalNode fill:#ddf4ff,stroke:#0969da,color:#24292f;
    class blank,schema,input_check,ready,output_check decision;
    class ui_error,validation_error,input_block,missing_index,query_error,output_block,show_error error;
    class prompt_guard,safeguard,llm externalNode;
```

## Notes

- The UI also rejects an empty question. FastAPI then validates the JSON request; invalid requests receive HTTP 422.
- The `/query` endpoint has no authentication middleware or authentication dependency configured, so requests proceed without a credential check.
- If Groq is configured, Prompt Guard checks the question and the safeguard model checks the generated answer. A guardrail rejection returns HTTP 422. If Groq is not configured or a guardrail call fails, the current implementation allows the request or answer through and logs the failure.
- A missing Qdrant collection returns HTTP 503. Other errors during query processing are returned as HTTP 500. The Streamlit UI displays API errors to the user.
- FastEmbed runs locally. OpenAI generates the response; Groq is used for the optional guardrail checks. Qdrant is the vector database.
- Documents enter Qdrant in a separate ingestion/reindex workflow. The per-question path only embeds the question, retrieves indexed passages, and generates a response.