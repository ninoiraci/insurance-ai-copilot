/**
 * Knowledge base browser + RAG Playground.
 *
 * The playground is deliberately raw: query in, chunks and similarity scores
 * out. It is the fastest way to show a reviewer what retrieval actually does,
 * including what happens when nothing matches.
 */

import { useState } from 'react';
import { ApiError, api } from '../api/client';
import { useApi, useMutation } from '../hooks/useApi';
import { Badge, EmptyState, ErrorState, Loading, Panel, Stat } from '../components/ui';
import type { AnswerResponse, KnowledgeDocument, SearchResponse } from '../types/api';
import { formatDate, humanise } from '../utils/format';

const EXAMPLE_QUERIES = [
  '¿Qué documentación necesito para un siniestro de coche?',
  '¿Cuál es el plazo para dar de baja una póliza?',
  '¿Qué pasa si se devuelve un recibo?',
  'zxqwv plurbo frimbulator',
];

export function KnowledgeBasePage() {
  const { data, loading, error, refetch } = useApi(() => api.knowledgeDocuments(), []);
  const [selected, setSelected] = useState<KnowledgeDocument | null>(null);
  const [loadingDoc, setLoadingDoc] = useState(false);
  const [docError, setDocError] = useState<string | null>(null);

  const ingest = useMutation((force: boolean) => api.ingestKnowledge(force));

  const openDocument = async (id: number) => {
    setLoadingDoc(true);
    setDocError(null);
    try {
      setSelected(await api.knowledgeDocument(id));
    } catch (cause) {
      // Without this the failure surfaced only as an unhandled rejection and
      // the viewer silently kept showing the previous document.
      setSelected(null);
      setDocError(cause instanceof ApiError ? cause.message : 'Could not load document');
    } finally {
      setLoadingDoc(false);
    }
  };

  const runIngest = async (force: boolean) => {
    const result = await ingest.run(force);
    if (result) refetch();
  };

  return (
    <div className="page stack">
      <div className="page__header">
        <div>
          <h1>Knowledge base</h1>
          <p className="page__subtitle">
            Synthetic internal procedure manuals. Documents are chunked on section
            boundaries, embedded and stored in the vector store; every generated answer must
            cite the chunks it used.
          </p>
        </div>
        <div className="row">
          <button
            type="button"
            className="btn btn--sm"
            onClick={() => runIngest(false)}
            disabled={ingest.pending}
          >
            {ingest.pending ? <><span className="spinner" /> Ingesting…</> : 'Ingest changes'}
          </button>
          <button
            type="button"
            className="btn btn--sm btn--primary"
            onClick={() => runIngest(true)}
            disabled={ingest.pending}
            title="Re-embeds every document, even unchanged ones"
          >
            Re-ingest all
          </button>
        </div>
      </div>

      {ingest.error && <ErrorState message={ingest.error} />}

      {loading && <Loading />}
      {error && !loading && <ErrorState message={error} onRetry={refetch} />}

      {data && !loading && (
        <>
          <div className="grid grid--stats">
            <Stat label="Documents" value={data.count} />
            <Stat
              label="Embedding model"
              value={<span className="text-sm">{data.embedding.model}</span>}
              hint={`${data.embedding.dimensions} dimensions · ${data.embedding.provider}`}
            />
            <Stat
              label="Vector backend"
              value={<span className="text-sm">{data.vector_backend}</span>}
              hint={
                data.vector_backend === 'pgvector'
                  ? 'Similarity computed in PostgreSQL'
                  : 'Similarity computed in Python (SQLite fallback)'
              }
            />
            <Stat
              label="Total chunks"
              value={data.items.reduce((sum, doc) => sum + doc.chunk_count, 0)}
            />
          </div>

          {data.embedding.provider === 'hashing' && (
            <div className="callout callout--info">
              <strong>Local hashing embeddings are lexical, not semantic.</strong> They match
              on shared words and character n-grams, so "coche" will not retrieve "vehículo"
              unless both appear. Set <code>EMBEDDING_PROVIDER=openai</code> for true semantic
              retrieval.
            </div>
          )}

          <RagPlayground />

          <div className="grid grid--two">
            <Panel title="Documents" hint={data.source_directory} flush>
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Title</th>
                      <th>Category</th>
                      <th>Chunks</th>
                      <th>Size</th>
                      <th>Ingested</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((document) => (
                      <tr
                        key={document.id}
                        className="is-clickable"
                        onClick={() => openDocument(document.id)}
                      >
                        <td className="table__primary">{document.title}</td>
                        <td>
                          <Badge tone="neutral">{humanise(document.category)}</Badge>
                        </td>
                        <td>{document.chunk_count}</td>
                        <td className="table__muted nowrap">
                          {(document.char_count / 1000).toFixed(1)}k chars
                        </td>
                        <td className="table__muted nowrap">
                          {formatDate(document.created_at)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>

            <Panel
              title={selected ? selected.title : 'Document viewer'}
              hint={selected ? `${selected.chunk_count} chunks` : 'select a document'}
            >
              {loadingDoc && <Loading />}
              {!loadingDoc && docError && <ErrorState message={docError} />}
              {!loadingDoc && !docError && !selected && (
                <EmptyState
                  title="No document selected"
                  hint="Click a row to read the source text and see how it was chunked."
                />
              )}
              {!loadingDoc && !docError && selected && (
                <div className="stack">
                  <div className="row text-xs muted">
                    <span className="mono">{selected.source_filename}</span>
                    <span>hash {selected.content_hash}</span>
                  </div>

                  <details>
                    <summary className="text-sm" style={{ cursor: 'pointer' }}>
                      Chunk boundaries ({selected.chunks?.length ?? 0})
                    </summary>
                    <div className="stack stack--sm mt-sm">
                      {selected.chunks?.map((chunk) => (
                        <div className="source" key={chunk.id}>
                          <div className="source__head">
                            <span className="source__title">
                              #{chunk.chunk_index} · {chunk.section ?? 'untitled'}
                            </span>
                          </div>
                          <div className="source__excerpt source__excerpt--open">
                            {chunk.content}
                          </div>
                        </div>
                      ))}
                    </div>
                  </details>

                  <div className="field">
                    <span className="field__label">Source document</span>
                    <div
                      className="source scroll-y max-480"
                      style={{ background: 'var(--surface)' }}
                    >
                      <div className="pre-wrap text-sm">{selected.raw_content}</div>
                    </div>
                  </div>
                </div>
              )}
            </Panel>
          </div>
        </>
      )}
    </div>
  );
}

function RagPlayground() {
  const [query, setQuery] = useState(EXAMPLE_QUERIES[0]);
  const [topK, setTopK] = useState(5);
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [answer, setAnswer] = useState<AnswerResponse | null>(null);

  const search = useMutation(() => api.searchKnowledge(query, topK));
  const generate = useMutation(() => api.answerFromKnowledge(query, topK));

  const runSearch = async () => {
    setAnswer(null);
    const result = await search.run();
    if (result) setResults(result);
  };

  const runAnswer = async () => {
    const result = await generate.run();
    if (result) {
      setAnswer(result);
      setResults({
        query: result.query,
        results: result.results,
        count: result.count,
        vector_backend: result.vector_backend,
        embedding: result.embedding,
        min_similarity: 0,
      });
    }
  };

  const busy = search.pending || generate.pending;

  return (
    <Panel
      title="RAG Playground"
      hint="retrieval and grounded generation, with scores"
    >
      <div className="filters">
        <div className="field field--grow">
          <label className="field__label" htmlFor="rag-query">
            Query
          </label>
          <input
            id="rag-query"
            className="input"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !busy) runSearch();
            }}
          />
        </div>
        <div className="field" style={{ minWidth: 96 }}>
          <label className="field__label" htmlFor="rag-topk">
            Top K
          </label>
          <select
            id="rag-topk"
            className="select"
            value={topK}
            onChange={(event) => setTopK(Number(event.target.value))}
          >
            {[3, 5, 8, 10].map((value) => (
              <option key={value} value={value}>{value}</option>
            ))}
          </select>
        </div>
        <button type="button" className="btn btn--primary" onClick={runSearch} disabled={busy}>
          {search.pending ? <><span className="spinner" /> Searching…</> : 'Search'}
        </button>
        <button
          type="button"
          className="btn"
          onClick={runAnswer}
          disabled={busy}
          title="Retrieve, then generate a grounded answer that must cite its sources"
        >
          {generate.pending ? <><span className="spinner" /> Generating…</> : 'Search + answer'}
        </button>
      </div>

      <div className="row mt-sm">
        <span className="text-xs muted">Try:</span>
        {EXAMPLE_QUERIES.map((example) => (
          <button
            key={example}
            type="button"
            className="btn btn--sm"
            onClick={() => setQuery(example)}
          >
            {example.length > 42 ? `${example.slice(0, 42)}…` : example}
          </button>
        ))}
      </div>

      {(search.error || generate.error) && (
        <div className="mt-md">
          <ErrorState message={search.error ?? generate.error ?? ''} />
        </div>
      )}

      {answer && (
        <div className="mt-md">
          <div
            className={
              answer.insufficient_information
                ? 'callout callout--warning'
                : 'callout callout--success'
            }
          >
            <strong>
              {answer.insufficient_information
                ? 'Insufficient information — refused'
                : 'Grounded answer'}
            </strong>
            <div className="pre-wrap mt-sm">{answer.answer}</div>
            {answer.used_sources.length > 0 && (
              <div className="mt-sm text-xs">
                Sources: {answer.used_sources.join(' · ')}
              </div>
            )}
          </div>
          <div className="row text-xs muted mt-sm">
            <span>model: {answer.metadata.model}</span>
            <span>prompt: {answer.metadata.prompt_version}</span>
            <span>{answer.metadata.latency_ms} ms</span>
            {answer.metadata.demo_mode && <Badge tone="warning">Demo AI</Badge>}
          </div>
        </div>
      )}

      {results && (
        <div className="mt-md">
          <div className="copilot__section-title">
            Retrieved chunks
            <span className="panel__hint">
              {results.count} results · backend {results.vector_backend}
            </span>
          </div>
          {results.results.length === 0 ? (
            <div className="callout callout--info">
              Nothing scored above the similarity floor. The system returns no sources rather
              than weak ones, and generation then refuses to answer.
            </div>
          ) : (
            results.results.map((chunk) => (
              <div className="source" key={chunk.chunk_id}>
                <div className="source__head">
                  <span className="source__title">{chunk.citation}</span>
                  <span className="source__score">
                    similarity {chunk.similarity.toFixed(3)}
                  </span>
                </div>
                <div className="source__excerpt source__excerpt--open">{chunk.content}</div>
              </div>
            ))
          )}
        </div>
      )}
    </Panel>
  );
}
