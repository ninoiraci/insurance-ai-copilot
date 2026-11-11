/** Left column: the raw conversation, exactly as it arrived. */

import type { Message } from '../types/api';
import { formatDateTime, humanise } from '../utils/format';

export function ConversationThread({
  messages,
  analysedMessageId,
}: {
  messages: Message[];
  analysedMessageId?: number | null;
}) {
  return (
    <div className="thread">
      {messages.map((message) => {
        const role = message.sender_type.toLowerCase();
        const isAnalysed = message.id === analysedMessageId;
        return (
          <article
            key={message.id}
            className={`message message--${role}${isAnalysed ? ' is-analysed' : ''}`}
          >
            <div className="message__meta">
              {humanise(message.sender_type)} · {formatDateTime(message.timestamp)}
              {isAnalysed && ' · analysed'}
            </div>
            <div className="message__bubble">{message.content}</div>
          </article>
        );
      })}
    </div>
  );
}
