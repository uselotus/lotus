import React, { FC, useEffect, useState } from "react";
import { Card, Button, Divider } from "antd";
import MetricTable from "../components/Metrics/MetricTable";
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
} from "../components/Metrics/CreateMetricForm";
import { toast } from "react-toastify";
import EventPreview from "../components/EventPreview";
import "./ViewMetrics.css";
import { PageLayout } from "../components/base/PageLayout";

const defaultMetricState: CreateMetricState = {
  title: "Create a new Metric",
  event_name: "",
  usage_aggregation_type: "count",
  property_name: "",
  metric_type: "counter",
  usage_aggregation_type_2: "max",
  property_name_2: "",
};

const ViewMetrics: FC = () => {
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

      onError: (error: any) => {
        toast.error("Error creating metric: " + error.response.data.detail, {
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
      usage_aggregation_type:
        state.metric_type === "stateful"
          ? state.usage_aggregation_type_2
          : state.usage_aggregation_type,
      property_name:
        state.metric_type == "stateful"
          ? state.property_name_2
          : state.property_name,
      granularity:
        state.metric_type === "stateful"
          ? state.granularity_2
          : state.granularity,
      billable_metric_name: state.billable_metric_name,
      metric_type: state.metric_type,
      billable_aggregation_type: state.billable_aggregation_type,
      //defaults for now
      event_type: state.metric_type === "stateful" ? state.event_type : "delta",
      is_cost_metric: state.is_cost_metric,
    };
    mutation.mutate(metricInstance);
  };

  return (
    <PageLayout
      title="Metrics"
      extra={[
        <Button
          type="primary"
          size="large"
          key={"create-plan"}
          onClick={createMetricButton}
        >
          Create Metric
        </Button>,
      ]}
    >
      <div className="flex flex-col space-y-4 bg-background">
        {isLoading || data === undefined ? (
          <div className="flex justify-center">
            <LoadingSpinner />{" "}
          </div>
        ) : (
          <MetricTable metricArray={data} />
        )}
        {isError && <div className=" text-danger">Something went wrong</div>}
        <Card className="flex flex-row justify-center h-full">
          <EventPreview />
        </Card>
        <CreateMetricForm
          state={metricState}
          visible={visible}
          onSave={onSave}
          onCancel={onCancel}
        />
      </div>
    </PageLayout>
  );
};

export default ViewMetrics;
