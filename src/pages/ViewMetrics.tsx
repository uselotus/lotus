import React, { FC, useEffect, useState } from "react";
import { Card, List, Skeleton, Button, Divider } from "antd";
import InfiniteScroll from "react-infinite-scroll-component";
import { useNavigate } from "react-router-dom";
import type { ProColumns } from "@ant-design/pro-components";
import { ProTable } from "@ant-design/pro-components";
import MetricTable from "../components/MetricTable";
import { Metrics } from "../api/api";
import { MetricType } from "../types/metric-type";
import { useQuery, UseQueryResult } from "react-query";
import LoadingSpinner from "../components/LoadingSpinner";

const ViewMetrics: FC = () => {
  const navigate = useNavigate();

  const { data, isLoading }: UseQueryResult<MetricType[]> = useQuery<
    MetricType[]
  >(["metric_list"], () =>
    Metrics.getMetrics().then((res) => {
      return res;
    })
  );

  const navigateCreatePlan = () => {
    navigate("/create-plan");
  };

  return (
    <div>
      <div className="flex flex-row w-full">
        <h1 className="text-3xl font-main mb-5">Billable Metrics</h1>
        <Button
          type="primary"
          className="ml-auto bg-info"
          onClick={navigateCreatePlan}
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
        <Card className="flex flex-row justify-center">
          <h1 className="text-2xl font-main mb-5">Event Stream</h1>
          <Divider />
        </Card>
      </div>
    </div>
  );
};

export default ViewMetrics;
