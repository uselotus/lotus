import React, { FC, useEffect, useState } from "react";
import BacktestTable from "../components/Experiments/BacktestTable";

import { Backtests } from "../api/api";
import LoadingSpinner from "../components/LoadingSpinner";
import { useQuery, UseQueryResult, useQueryClient } from "react-query";
import { PageLayout } from "../components/base/PageLayout";
import { BacktestType } from "../types/experiment-type";
import { Button } from "antd";
import { useNavigate } from "react-router-dom";

const backtest_data: BacktestType[] = [
  {
    backtest_name: "Name",
    backtest_id: "id",
    status: "status",
    start_time: "2022-23-02",
    end_time: "2022-20-03",
    time_created: "2022-20-02",
    kpis: ["revenue"],
  },
];

const ViewExperiments: FC = () => {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const { data, isLoading }: UseQueryResult<BacktestType[]> = useQuery<
    BacktestType[]
  >(["experiments_list"], () =>
    Backtests.getBacktests().then((res) => {
      return res;
    })
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
          className="bg-black text-white justify-self-end"
          size="large"
          key={"create-plan"}
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
            <h3>Backtests</h3>
            <BacktestTable backtests={backtest_data} />
          </div>
        )}
      </div>
    </PageLayout>
  );
};

export default ViewExperiments;
