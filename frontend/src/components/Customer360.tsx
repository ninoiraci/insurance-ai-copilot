/**
 * Centre column: Customer 360.
 *
 * This shows exactly the context object that was handed to the model, which is
 * what makes "why did it decide that?" answerable — including the policy
 * expiry dates that drive the deterministic urgency rules.
 */

import { Link } from 'react-router-dom';
import type { Customer, CustomerContext, Task } from '../types/api';
import {
  channelIcon,
  expiryTone,
  formatDate,
  humanise,
  urgencyTone,
} from '../utils/format';
import { Badge, EmptyState } from './ui';

export function Customer360({
  customer,
  context,
  tasks,
}: {
  customer: Customer;
  context: CustomerContext;
  tasks: Task[];
}) {
  const openTasks = tasks.filter((task) => task.status !== 'DONE');

  return (
    <div>
      <section className="copilot__section">
        <div className="copilot__section-title">
          Profile
          <Link className="text-xs" to={`/customers/${customer.id}`}>
            Full record →
          </Link>
        </div>
        <div className="kv">
          <span className="kv__key">Name</span>
          <span className="kv__value">{customer.full_name}</span>
          <span className="kv__key">Email</span>
          <span className="kv__value">{customer.email ?? '—'}</span>
          <span className="kv__key">Phone</span>
          <span className="kv__value">{customer.phone ?? '—'}</span>
          <span className="kv__key">City</span>
          <span className="kv__value">{customer.city ?? '—'}</span>
          <span className="kv__key">Language</span>
          <span className="kv__value">{customer.preferred_language.toUpperCase()}</span>
        </div>
      </section>

      <section className="copilot__section">
        <div className="copilot__section-title">
          Policies
          <span className="panel__hint">{context.policies.length} active</span>
        </div>
        {context.policies.length === 0 ? (
          <p className="text-sm muted">No active policies on record.</p>
        ) : (
          <div className="stack stack--sm">
            {context.policies.map((policy) => (
              <div className="source" key={policy.policy_number}>
                <div className="source__head">
                  <span className="source__title">
                    {humanise(policy.policy_type)} · {policy.policy_number}
                  </span>
                  <Badge tone={expiryTone(policy.days_to_expiration)}>
                    {policy.days_to_expiration < 0
                      ? `expired ${Math.abs(policy.days_to_expiration)}d ago`
                      : `${policy.days_to_expiration}d left`}
                  </Badge>
                </div>
                <div className="text-xs muted">
                  {policy.provider} · expires {formatDate(policy.expiration_date)} ·{' '}
                  {humanise(policy.status)}
                  {policy.vehicle_plate ? ` · plate ${policy.vehicle_plate}` : ''}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="copilot__section">
        <div className="copilot__section-title">Previous interactions</div>
        {context.recent_interactions.length === 0 ? (
          <p className="text-sm muted">No earlier conversations.</p>
        ) : (
          <ul className="list-plain">
            {context.recent_interactions.map((interaction, index) => (
              <li key={`${interaction.date}-${index}`}>
                {channelIcon(interaction.channel)} {interaction.subject}{' '}
                <span className="muted text-xs">
                  ({formatDate(interaction.date)}, {humanise(interaction.status)})
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="copilot__section">
        <div className="copilot__section-title">
          Tasks on this case
          <span className="panel__hint">{openTasks.length} open</span>
        </div>
        {tasks.length === 0 ? (
          <EmptyState
            title="No tasks yet"
            hint="The action engine creates one when the conversation is analysed."
          />
        ) : (
          <div className="stack stack--sm">
            {tasks.map((task) => (
              <div className="source" key={task.id}>
                <div className="source__head">
                  <span className="source__title">{task.title}</span>
                  <Badge tone={urgencyTone[task.priority]}>{task.priority}</Badge>
                </div>
                <div className="text-xs muted">
                  {humanise(task.assigned_team)} · {humanise(task.status)}
                  {task.due_at ? ` · due ${formatDate(task.due_at)}` : ''}
                </div>
                {task.description && (
                  <div className="source__excerpt source__excerpt--open mt-sm">
                    {task.description}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
