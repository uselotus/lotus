import React, { FC } from "react";
import { useQuery, UseQueryResult, useQueryClient } from '@tanstack/react-query';
import { Button } from "antd";
import { useNavigate } from "react-router-dom";
import ExperimentsTable from "../components/Experiments/ExperimentsTable";

import { Backtests, Experiments } from "../api/api";
import LoadingSpinner from "../components/LoadingSpinner";
import { PageLayout } from "../components/base/PageLayout";
import { BacktestType } from "../types/experiment-type";
import { components } from "../gen-types";

const ViewExperiments: FC = () => {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const {
    data,
    isLoading,
  }: UseQueryResult<components["schemas"]["AnalysisSummary"][]> = useQuery<
    components["schemas"]["AnalysisSummary"][]
  >(
    ["experiments_list"],
    () => Experiments.getExperiments().then((res) => res),
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
            <ExperimentsTable backtests={data} />
          </div>
        )}
      </div>
    </PageLayout>
  );
};

export default ViewExperiments;
