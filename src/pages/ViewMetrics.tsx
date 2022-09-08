import React, { FC, useEffect, useState } from "react";
import { Card, List, Skeleton, Button, Divider } from "antd";
import { useNavigate } from "react-router-dom";
import MetricTable from "../components/MetricTable";
import { Metrics } from "../api/api";
import { MetricType } from "../types/metric-type";
import { useQuery, UseQueryResult, useMutation } from "react-query";
import LoadingSpinner from "../components/LoadingSpinner";
import CreateMetricForm, {
  CreateMetricState,
} from "../components/CreateMetricForm";
import { toast, ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";

const defaultMetricState: CreateMetricState = {
  title: "Create a new Metric",
  event_name: "",
  aggregation_type: "",
  property_name: "",
};

const ViewMetrics: FC = () => {
  const navigate = useNavigate();
  const [visible, setVisible] = useState<boolean>(false);
  const [metricState, setMetricState] =
    useState<CreateMetricState>(defaultMetricState);

  const { data, isLoading }: UseQueryResult<MetricType[]> = useQuery<
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
    };
    mutation.mutate(metricInstance);
  };

  return (
    <div>
      <div className="flex flex-row w-full">
        <h1 className="text-3xl font-main mb-5">Billable Metrics</h1>
        <Button
          type="primary"
          className="ml-auto bg-info"
          onClick={createMetricButton}
        >
          Create Metric
        </Button>
      </div>

      <div className="grid grid-cols-2">
        <div>
          {isLoading || data === undefined ? (
            <LoadingSpinner />
          ) : (
            <MetricTable metricArray={data} />
          )}
        </div>
        <Card className="flex flex-row justify-center bg-light">
          <h1 className="text-2xl font-main mb-5">Event Stream</h1>
          <Divider />
          <div>
            <p className=" text-bold">
              Realtime Event Stream Preivew Coming Soon
            </p>
          </div>
        </Card>
      </div>
      <CreateMetricForm
        state={metricState}
        visible={visible}
        onSave={onSave}
        onCancel={onCancel}
      />
      <ToastContainer />
    </div>
  );
};

export default ViewMetrics;
