import React, { FC, useEffect, useState } from "react";
import { Card, Button, Divider } from "antd";
import MetricTable from "../components/Metrics/MetricTable";
import { Metrics } from "../api/api";
import {
  CateogricalFilterType,
  MetricType,
  NumericFilterType,
} from "../types/metric-type";
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
  metric_id: "",
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
      granularity: state.metric_type === "rate" ? state.granularity : "total",
      proration:
        state.metric_type === "stateful"
          ? state.granularity_2
          : state.granularity,
      metric_name: state.metric_name,
      metric_type: state.metric_type,
      billable_aggregation_type: state.billable_aggregation_type,
      //defaults for now
      event_type: state.metric_type === "stateful" ? state.event_type : "delta",
      is_cost_metric: state.is_cost_metric,
      custom_sql: state.metric_type === "custom" ? state.custom_sql : undefined,
      metric_id: "",
    };

    if (state.filters) {
      const numericFilters: NumericFilterType[] = [];
      const categoricalFilters: CateogricalFilterType[] = [];
      for (let i = 0; i < state.filters.length; i++) {
        if (
          state.filters[i].operator === "isin" ||
          state.filters[i].operator === "isnotin"
        ) {
          categoricalFilters.push({
            property_name: state.filters[i].property_name,
            operator: state.filters[i].operator,
            comparison_value: [state.filters[i].comparison_value],
          });
        } else {
          numericFilters.push({
            property_name: state.filters[i].property_name,
            operator: state.filters[i].operator,
            comparison_value: parseFloat(state.filters[i].comparison_value),
          });
        }
      }
      metricInstance.numeric_filters = numericFilters;
      metricInstance.categorical_filters = categoricalFilters;
    }

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
          <div className="flex align-center justify-center min-h-[100px] bg-white">
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
