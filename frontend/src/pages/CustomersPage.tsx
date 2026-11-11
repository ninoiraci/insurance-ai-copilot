/** Searchable customer list. */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useApi, useDebounced } from '../hooks/useApi';
import { EmptyState, ErrorState, Loading, Panel } from '../components/ui';
import { formatDate } from '../utils/format';

export function CustomersPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const debounced = useDebounced(search);

  const { data, loading, error, refetch } = useApi(
    () => api.customers(debounced || undefined),
    [debounced],
  );

  return (
    <div className="page stack">
      <div className="page__header">
        <div>
          <h1>Customers</h1>
          <p className="page__subtitle">
            Synthetic customer book. Open a record for policies, conversation history, tasks
            and the AI case history.
          </p>
        </div>
      </div>

      <Panel title="Search">
        <div className="filters">
          <div className="field field--grow">
            <label className="field__label" htmlFor="customer-search">
              Name, email, phone or city
            </label>
            <input
              id="customer-search"
              className="input"
              placeholder="e.g. Carlos, Madrid…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          {search && (
            <button type="button" className="btn btn--sm" onClick={() => setSearch('')}>
              Clear
            </button>
          )}
        </div>
      </Panel>

      <Panel title="Customer book" hint={data ? `${data.count} customers` : undefined} flush>
        {loading && <Loading />}
        {error && !loading && (
          <div style={{ padding: 16 }}>
            <ErrorState message={error} onRetry={refetch} />
          </div>
        )}
        {data && !loading && data.items.length === 0 && (
          <EmptyState title="No customers match this search" />
        )}
        {data && !loading && data.items.length > 0 && (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Phone</th>
                  <th>City</th>
                  <th>Policies</th>
                  <th>Conversations</th>
                  <th>Open tasks</th>
                  <th>Customer since</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((customer) => (
                  <tr
                    key={customer.id}
                    className="is-clickable"
                    onClick={() => navigate(`/customers/${customer.id}`)}
                  >
                    <td className="table__primary">{customer.full_name}</td>
                    <td className="table__muted">{customer.email ?? '—'}</td>
                    <td className="table__muted nowrap">{customer.phone ?? '—'}</td>
                    <td>{customer.city ?? '—'}</td>
                    <td>{customer.policy_count ?? 0}</td>
                    <td>{customer.conversation_count ?? 0}</td>
                    <td>{customer.open_task_count ?? 0}</td>
                    <td className="table__muted nowrap">{formatDate(customer.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}
