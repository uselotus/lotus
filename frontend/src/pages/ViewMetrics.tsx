import React, { FC, useEffect, useState } from "react";
import { Card, Button, Divider } from "antd";
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
import EventPreview from "../components/EventPreview";
import "./ViewMetrics.css";
import { PageLayout } from "../components/base/PageLayout";

const defaultMetricState: CreateMetricState = {
  title: "Create a new Metric",
  event_name: "",
  aggregation_type: "count",
  property_name: "",
  metric_type: "",
  aggregation_type_2: "max",
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
      aggregation_type:
        state.metric_type === "stateful"
          ? state.aggregation_type_2
          : state.aggregation_type,
      property_name:
        state.metric_type == "stateful"
          ? state.property_name_2
          : state.property_name,
      billable_metric_name: state.billable_metric_name,
      metric_type: state.metric_type,
    };
    mutation.mutate(metricInstance);
  };

  return (
    <PageLayout
      title="Metrics"
      extra={[
        <Button
          className="bg-black text-white justify-self-end"
          size="large"
          key={"create-plan"}
          onClick={createMetricButton}
        >
          Create Metric
        </Button>,
      ]}
    >
      <div>
        <div className="grid grid-cols-2">
          <div className="flex flex-col">
            {isLoading || data === undefined ? (
              <LoadingSpinner />
            ) : (
              <MetricTable metricArray={data} />
            )}
            {isError && (
              <div className=" text-danger">Something went wrong</div>
            )}
          </div>
          <Card className="flex flex-row justify-center bg-light h-full">
            <h1 className="text-2xl font-main mb-5">Event Stream</h1>
            <Divider />
            <div>
              <EventPreview />
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
    </PageLayout>
  );
};

export default ViewMetrics;
