// @ts-ignore
import React, { FC } from "react";
import BacktestTable from "../components/Experiments/BacktestTable";

import { Backtests } from "../api/api";
import LoadingSpinner from "../components/LoadingSpinner";
import { useQuery, UseQueryResult, useQueryClient } from "react-query";
import { PageLayout } from "../components/base/PageLayout";
import { BacktestType } from "../types/experiment-type";
import { useNavigate } from "react-router-dom";
import {LotusButton} from "../components/base/Button";

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
      extra={[<LotusButton text="Create Experiment" onClick={navigateCreatePlan}/>]}
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
