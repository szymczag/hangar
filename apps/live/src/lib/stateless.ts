/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { IncomingMessage, MessageType } from "@hocuspocus/server";
import type { beforeHandleMessagePayload, onStatelessPayload } from "@hocuspocus/server";
import { DocumentCollaborativeEvents } from "@plane/editor/lib";
import type { TDocumentEventsServer } from "@plane/editor/lib";

/**
 * Broadcast the client event to all the clients so that they can update their state
 * @param param0
 */
export const onStateless = async ({ payload, document, connection }: onStatelessPayload) => {
  const response = DocumentCollaborativeEvents[payload as TDocumentEventsServer]?.client;
  // A read-only connection may not announce page events to the other clients.
  if (response && !connection.readOnly) {
    document.broadcastStateless(response);
  }
};

/**
 * Hocuspocus relays a client's BroadcastStateless message to every connection on the document, read-only ones
 * included, with no hook to veto the payload. Clients have no use for it: page events go through onStateless above,
 * and server notices (force_close, Redis broadcasts) are sent by the server itself. Refusing it here also stops a
 * guest from telling other clients to stop reconnecting. A refused message closes the sender's connection to this
 * document: Hocuspocus sends it a CLOSE for the document with this code and reason, and nothing more is synced to it
 * until it authenticates again (still read-only for a guest). The WebSocket itself stays open.
 */
export const beforeHandleMessage = async ({ update }: beforeHandleMessagePayload) => {
  const message = new IncomingMessage(update);
  message.readVarString(); // document name, already matched by the connection
  if (message.readVarUint() === MessageType.BroadcastStateless) {
    throw Object.assign(new Error("Clients may not broadcast stateless messages"), {
      code: 4403,
      reason: "broadcast-stateless-refused",
    });
  }
};
