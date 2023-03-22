import React, { FC } from "react";
import { useQuery, UseQueryResult, useQueryClient } from '@tanstack/react-query';
import { Button } from "antd";
import { useNavigate } from "react-router-dom";
import BacktestTable from "../components/Experiments/BacktestTable";

import { Backtests } from "../api/api";
import LoadingSpinner from "../components/LoadingSpinner";
import { PageLayout } from "../components/base/PageLayout";
import { BacktestType } from "../types/experiment-type";

const ViewExperiments: FC = () => {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const { data, isLoading }: UseQueryResult<BacktestType[]> = useQuery<
    BacktestType[]
  >(
    ["experiments_list"],
    () =>
      Backtests.getBacktests().then((res) => res),
    {
      // Refetch the data every second
      refetchInterval: 5000,
    }
  );

  const navigateCreateExperiment = () => {
    navigate("/create-experiment");
  };

  return (
    <PageLayout
      title="Experiments (beta)"
      extra={[
        <Button
          onClick={navigateCreateExperiment}
          className="text-white"
          size="large"
          key="create-plan"
          type="primary"
          disabled
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
