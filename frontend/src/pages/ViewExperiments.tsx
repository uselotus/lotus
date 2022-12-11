import React, { FC, useEffect, useState } from "react";
import BacktestTable from "../components/Experiments/BacktestTable";

import { Backtests } from "../api/api";
import LoadingSpinner from "../components/LoadingSpinner";
import { useQuery, UseQueryResult, useQueryClient } from "react-query";
import { PageLayout } from "../components/base/PageLayout";
import { BacktestType } from "../types/experiment-type";
import { Button } from "antd";
import { useNavigate } from "react-router-dom";

const ViewExperiments: FC = () => {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const { data, isLoading }: UseQueryResult<BacktestType[]> = useQuery<
    BacktestType[]
  >(
    ["experiments_list"],
    () =>
      Backtests.getBacktests().then((res) => {
        return res;
      }),
    {
      // Refetch the data every second
      refetchInterval: 5000,
    }
  );

  const navigateCreatePlan = () => {
    navigate("/create-experiment");
  };

  return (
    <PageLayout
      title="Experiments"
      extra={[
        <Button
          onClick={navigateCreatePlan}
          className="text-white"
          size="large"
          key={"create-plan"}
          type="primary"
          disabled={true}
        >
          Create Experiment
        </Button>,
      ]}
    >
      <div>
        {isLoading || data === undefined ? (
          <LoadingSpinner />
        ) : (
          <div>
            <BacktestTable backtests={data} />
          </div>
        )}
      </div>
    </PageLayout>
  );
};

export default ViewExperiments;
