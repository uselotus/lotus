import { useCallback, useEffect, useState, useRef } from "react";
import { useQuery, UseQueryResult, useQueryClient } from "react-query";

import useDebounce from "../../hooks/useDebounce";
import { Events } from "../../api/api";
import { EventPages, EventPreviewType } from "../../types/event-type";

type EventStream = EventPreviewType[];

export interface UseEventStreamProps {
  stream: boolean;
  query: {
    customer_id?: string | undefined;
    idempotency_id?: string | undefined;
  };
  refreshRate?: number;
  pageSize?: number;
}

function spliceEvents(events: EventStream, newEvents: EventStream) {
  const idempotencySet = new Set(events.map((event) => event.idempotency_id));
  const uniqueEvents = newEvents.filter(
    (event) => !idempotencySet.has(event.idempotency_id)
  );
  // sort events by dates
  return events.concat(uniqueEvents).sort((ev1, ev2) => {
    const date1 = new Date(ev1.time_created);
    const date2 = new Date(ev2.time_created);
    return date2.getTime() - date1.getTime();
  });
}

function parseCursor(cursor: string) {
  // Server returns an invalid cursor, this parses that cursor and returns a valid one
  // Def is a bandaid and should be fixed server side
  return cursor.split("&")[0];
}

export default function useEventStream({
  stream,
  query,
  refreshRate = 5000,
  pageSize = 10,
}: UseEventStreamProps) {
  const [events, setEvents] = useState<EventPreviewType[]>([]);
  const [eventIdx, setEventIdx] = useState<number>(0);

  const [pageCursor, setPageCursor] = useState<string>("");
  const [pageNext, setPageNext] = useState<string>("");
  const [pagePrev, setPagePrev] = useState<string>();

  const [streaming, setStreaming] = useState(stream);
  const idempotencySet = useRef<Set<string>>(new Set());
  const streamCursor = useRef("");

  // Queries for page scroll data
  const queryClient = useQueryClient();

  useEffect(() => {
    setEvents([]);
    setEventIdx(0);
    setPageCursor("");
    setPageNext("");
    setPagePrev("");
    idempotencySet.current.clear();
    streamCursor.current = "";
  }, [JSON.stringify(query)]);

  const queryFn = useCallback(
    (c: string): Promise<EventPages> => {
      if (query.customer_id?.length || query.idempotency_id?.length) {
        return Events.searchEventPreviews({
          ...query,
          c,
        });
      } else {
        return Events.getEventPreviews(c);
      }
    },
    [JSON.stringify(query)]
  );

  // Polls for new event previews
  const { data: streamEventPages } = useQuery<EventPages>({
    queryFn: () => queryFn(streamCursor.current),
    refetchInterval: (data, query) => {
      if (!data || data.results.length === 0) {
        // no previews added
        streamCursor.current = "";
        return refreshRate;
      }
      for (const eventPreview of data.results) {
        if (idempotencySet.current.has(eventPreview.idempotency_id)) {
          // Means that we are starting to query already queried previewEvents
          streamCursor.current = "";
          return refreshRate;
        }
      }

      // There are more to start grabbing, execute immediately
      streamCursor.current = data.next;
      return 0;
    },
    enabled: streaming,
  });

  //
  const { data: eventPages } = useQuery<EventPages>({
    queryKey: ["preview_events", pageCursor, query],
    queryFn: () => queryFn(pageCursor),
  });

  useEffect(() => {
    queryClient.prefetchQuery({
      queryKey: ["preview_events", pageNext, query],
      queryFn: () => queryFn(pageNext),
    });
  }, [pageNext]);

  useEffect(() => {
    if (!streamEventPages) return;

    streamEventPages.results.forEach((newEvent) =>
      idempotencySet.current.add(newEvent.idempotency_id)
    );
    setEvents(spliceEvents(events, streamEventPages.results));
  }, [streamEventPages]);

  useEffect(() => {
    if (!eventPages) return;

    eventPages.results.forEach((newEvent) =>
      idempotencySet.current.add(newEvent.idempotency_id)
    );
    setEvents(spliceEvents(events, eventPages.results));
    setPageNext(parseCursor(decodeURIComponent(eventPages.next)));
    setPagePrev(parseCursor(decodeURIComponent(eventPages.previous)));
  }, [eventPages]);

  // Callbacks

  const start = useCallback(() => {
    setEventIdx(0);
  }, []);

  const next = useCallback(() => {
    if (eventIdx >= events.length - pageSize) {
      setPageCursor(parseCursor(pageNext));
    }
    setEventIdx(eventIdx + pageSize);
  }, [pageNext, eventIdx]);

  const prev = useCallback(() => {
    if (eventIdx >= pageSize) {
      setEventIdx(eventIdx - pageSize);
    } else {
      setEventIdx(0);
    }
  }, [pagePrev, eventIdx]);

  const page = useDebounce(events.slice(eventIdx, eventIdx + pageSize), 10);

  return {
    pageIndex: Math.floor(eventIdx / pageSize) + 1,
    page,
    streaming,
    start,
    next,
    prev,
    setStreaming,
  };
}
