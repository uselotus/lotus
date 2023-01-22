import React, { FC, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Select, Button } from "antd";
import { Card, Flex, Metric } from "@tremor/react";
import { ArrowLeftOutlined } from "@ant-design/icons";
import { useQuery, UseQueryResult } from "react-query";
import { Backtests } from "../api/api";
import { BacktestResultType, SpecificResults } from "../types/experiment-type";
import { PageLayout } from "../components/base/PageLayout";
import BacktestSubstitution from "../components/Experiments/BacktestSubsitution";
import dayjs from "dayjs";
import LoadingSpinner from "../components/LoadingSpinner";

const arrowURL = new URL("../components/arrow.svg", import.meta.url).href;

const { Option } = Select;

const fakeData = [
  { date: "2019-03", original_plan_revenue: 350, new_plan_revenue: 200 },
  { date: "2019-04", original_plan_revenue: 900, new_plan_revenue: 300 },
  { date: "2019-05", original_plan_revenue: 300, new_plan_revenue: 400 },
  { date: "2019-06", original_plan_revenue: 450, new_plan_revenue: 500 },
  { date: "2019-07", original_plan_revenue: 470, new_plan_revenue: 600 },
];

const ExperimentResults: FC = () => {
  const params = useParams();
  const navigate = useNavigate();
  const { experimentId } = params as any;
  const [selectedSubstitution, setSelectedSubstitution] = React.useState<
    SpecificResults | undefined
  >();

  const {
    data: experiment,
    isLoading,
    isError,
  }: UseQueryResult<BacktestResultType> = useQuery<BacktestResultType>(
    ["experiment_results", experimentId],
    () =>
      Backtests.getBacktestResults(experimentId).then(
        (res: BacktestResultType) => {
          return res;
        }
      )
  );

  const changeSubstitution = (value: string) => {
    const selectedSubstitution =
      experiment?.backtest_results.substitution_results.find(
        (substitution) => substitution.substitution_name === value
      );
    setSelectedSubstitution(selectedSubstitution);
  };

  useEffect(() => {
    if (
      experiment &&
      experiment.backtest_results.substitution_results.length > 0
    ) {
      setSelectedSubstitution(
        experiment?.backtest_results.substitution_results[0]
      );
    }
  }, [experiment]);

  const goBackPage = () => {
    navigate(-1);
  };

  const dataFormatter = (number: number) => `$${number.toFixed(2)}`;

  if (isLoading) {
    return (
      <div className="flex h-screen">
        <div className="m-auto">
          <LoadingSpinner />
        </div>
      </div>
    );
  }

  return (
    <PageLayout
      title="Results"
      extra={[
        <Button
          key={"back"}
          onClick={goBackPage}
          icon={<ArrowLeftOutlined />}
          type="default"
          size="large"
        >
          Back
        </Button>,
      ]}
    >
      {isError || experiment === undefined ? (
        <div>Something went wrong</div>
      ) : (
        <div className="">
          <div className="grid grid-cols-3 gap-4">
            <div className="col-span-1 border-2 border-solid rounded border-[#EAEAEB] px-6 py-6 bg-white">
              <div className="grid grid-cols-1 gap-6">
                <div className="mb-3">
                  <h2 className="font-bold">{experiment?.backtest_name}</h2>
                </div>
                <h3 className="font-bold">
                  Date Run:{" "}
                  {dayjs(experiment.time_created).format("YYYY-MM-DD")}
                </h3>

                <div className=" col-span-1 self-center">
                  <h3 className=" font-bold">
                    Date Range: {experiment.start_date} to {experiment.end_date}
                  </h3>
                </div>
                <div className="col-span-1">
                  <h3 className=" font-bold">Status: {experiment.status}</h3>
                </div>
              </div>
            </div>
            <div className="col-span-2 flex flex-col border-2 col border-solid rounded border-[#EAEAEB] px-6 py-6 bg-white ">
              <div className="flex flex-row space-x-8 content-center	 ">
                <h2> Substitutions</h2>
                <Select
                  defaultValue="Select a substitution"
                  className=" w-full"
                  onChange={changeSubstitution}
                  value={selectedSubstitution?.substitution_name}
                  showArrow={false}
                >
                  {experiment.backtest_results.substitution_results.map(
                    (substitution) => (
                      <Option
                        key={substitution.substitution_name}
                        value={substitution.substitution_name}
                      >
                        {substitution.substitution_name}
                      </Option>
                    )
                  )}
                </Select>
              </div>

              <div className="">
                {selectedSubstitution && (
                  <div className="grid grid-cols-3 gap-3 justify-between m-3">
                    <div className="w-full mt-6">
                      <Card key={234}>
                        <div className="justify-center">
                          <h3>
                            Plan:{" "}
                            {selectedSubstitution?.original_plan.plan_name}
                          </h3>

                          <Metric>
                            {dataFormatter(
                              selectedSubstitution.original_plan.plan_revenue
                            )}
                          </Metric>
                        </div>
                      </Card>
                    </div>
                    <div className="justify-self-center self-center	mt-6">
                      <img src={arrowURL} alt="arrow" className="mb-4" />
                    </div>
                    <div className="w-full mt-6">
                      <Card key={232342}>
                        <Flex
                          justifyContent="justify-between"
                          alignItems="items-start"
                          spaceX="space-x-6"
                        >
                          <h3>
                            Plan: {selectedSubstitution?.new_plan.plan_name}
                          </h3>
                          <h3
                            className={[
                              "",
                              selectedSubstitution.pct_revenue_change >= 0
                                ? "text-green"
                                : "text-red",
                            ].join("")}
                          >
                            {(
                              selectedSubstitution.pct_revenue_change * 100
                            ).toFixed(2) + "%"}
                          </h3>
                        </Flex>
                        <Metric>
                          {dataFormatter(
                            selectedSubstitution.new_plan.plan_revenue
                          )}
                        </Metric>
                      </Card>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
          {selectedSubstitution && (
            <BacktestSubstitution substitution={selectedSubstitution} />
          )}
        </div>
      )}
    </PageLayout>
  );
};

export default ExperimentResults;
