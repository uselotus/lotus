import React, { FC, useEffect, useState } from "react";
import { Card, List, Skeleton, Button, Divider } from "antd";
import { useNavigate } from "react-router-dom";
import MetricTable from "../components/MetricTable";
import { Metrics } from "../api/api";
import { MetricType } from "../types/metric-type";
import {
  useQuery,
  UseQueryResult,
  useMutation,
  useQueryClient,
} from "react-query";
import LoadingSpinner from "../components/LoadingSpinner";
import CreateMetricForm, {
  CreateMetricState,
} from "../components/CreateMetricForm";
import { toast } from "react-toastify";
import EventPreivew from "../components/EventPreview";
import "./ViewMetrics.css";

const defaultMetricState: CreateMetricState = {
  title: "Create a new Metric",
  event_name: "",
  aggregation_type: "",
  property_name: "",
  event_type: "",
  stateful_aggregation_period: "",
};

const ViewMetrics: FC = () => {
  const navigate = useNavigate();
  const [visible, setVisible] = useState<boolean>(false);
  const [metricState, setMetricState] =
    useState<CreateMetricState>(defaultMetricState);

  const queryClient = useQueryClient();

  const { data, isLoading, isError }: UseQueryResult<MetricType[]> = useQuery<
    MetricType[]
  >(["metric_list"], () =>
    Metrics.getMetrics().then((res) => {
      return res;
    })
  );

  const mutation = useMutation(
    (post: MetricType) => Metrics.createMetric(post),
    {
      onSuccess: () => {
        setVisible(false);
        queryClient.invalidateQueries(["metric_list"]);
        toast.success("Successfully created metric", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
    }
  );
  const createMetricButton = () => {
    setMetricState(defaultMetricState);
    setVisible(true);
  };

  const onCancel = () => {
    setVisible(false);
  };

  const onSave = (state: CreateMetricState) => {
    const metricInstance: MetricType = {
      event_name: state.event_name,
      aggregation_type: state.aggregation_type,
      property_name: state.property_name,
      billable_metric_name: state.billable_metric_name,
      event_type: state.event_type,
      stateful_aggregation_period: state.stateful_aggregation_period,
    };
    mutation.mutate(metricInstance);
  };

  return (
    <div>
      <div className="flex flex-row w-full">
        <h1 className="text-3xl font-main mb-5">Metrics</h1>
        <Button
          type="primary"
          className="ml-auto bg-info"
          onClick={createMetricButton}
        >
          Create Metric
        </Button>
      </div>

      <div className="grid grid-cols-2">
        <div className="flex flex-col">
          {isLoading || data === undefined ? (
            <LoadingSpinner />
          ) : (
            <MetricTable metricArray={data} />
          )}
          {isError && <div className=" text-danger">Something went wrong</div>}
        </div>
        <Card className="flex flex-row justify-center bg-light h-full">
          <h1 className="text-2xl font-main mb-5">Event Stream</h1>
          <Divider />
          <div>
            <EventPreivew />
          </div>
        </Card>
      </div>
      <CreateMetricForm
        state={metricState}
        visible={visible}
        onSave={onSave}
        onCancel={onCancel}
      />
    </div>
  );
};

export default ViewMetrics;
