-- Lokalt testskema og opdigtede testdata.
-- Må kun køres mod den lokale testdatabase. Brug aldrig rigtige CPR-numre.

DROP TABLE IF EXISTS order_event;
DROP TABLE IF EXISTS attestation_order;
DROP TABLE IF EXISTS attestation_request;

CREATE TABLE attestation_request (
    request_id text PRIMARY KEY,
    requested_at timestamptz NOT NULL DEFAULT now(),
    requester_name text NOT NULL,
    requester_email text NOT NULL,
    requester_dq text NOT NULL,
    subject_cpr text NOT NULL
);

CREATE TABLE attestation_order (
    order_id text PRIMARY KEY,
    request_id text NOT NULL REFERENCES attestation_request(request_id),
    attest_type integer NOT NULL,
    attest_subtype integer,
    status text NOT NULL,
    ordered_at timestamptz
);

CREATE TABLE order_event (
    event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id text NOT NULL REFERENCES attestation_order(order_id),
    status text NOT NULL,
    actor text NOT NULL,
    rejection_reason varchar(50),
    rejection_description text,
    occurred_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO attestation_request
    (request_id, requester_name, requester_email, requester_dq, subject_cpr)
VALUES
    ('demo-request-1', 'Test Rekvirent A', 'rekvirent-a@example.invalid', 'test-dq-1', 'TEST-CPR-1'),
    ('demo-request-2', 'Test Rekvirent B', 'rekvirent-b@example.invalid', 'test-dq-2', 'TEST-CPR-2');

INSERT INTO attestation_order
    (order_id, request_id, attest_type, attest_subtype, status)
VALUES
    ('demo-order-1', 'demo-request-1', 0, 0, 'pending_order'),
    ('demo-order-2', 'demo-request-2', 1, NULL, 'pending_order');