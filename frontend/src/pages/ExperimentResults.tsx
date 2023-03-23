import React, { FC, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Select, Button } from "antd";
import { Card, Flex, Metric } from "@tremor/react";
import { ArrowLeftOutlined } from "@ant-design/icons";
import { useQuery, UseQueryResult } from "@tanstack/react-query";
import dayjs from "dayjs";
import { Experiments } from "../api/api";
import { BacktestResultType, SpecificResults } from "../types/experiment-type";
import { PageLayout } from "../components/base/PageLayout";
import BacktestSubstitution from "../components/Experiments/BacktestSubsitution";
import LoadingSpinner from "../components/LoadingSpinner";
import { components } from "../gen-types";
import ExperimentDetails from "../components/Experiments/ExperimentDetails";

const arrowURL = new URL("../components/arrow.svg", import.meta.url).href;

const { Option } = Select;

const dummyData: components["schemas"]["AnalysisDetail"] = {
  time_created: "2022-03-22T10:30:00Z",
  analysis_name: "March 2022 Revenue Analysis",
  kpis: ["total_revenue"],
  status: "completed",
  start_date: "2022-03-01",
  end_date: "2022-03-22",
  analysis_results: {
    analysis_summary: [
      {
        plan: {
          plan_name: "Basic Plan",
          plan_id: "BSC-01",
          version_id: "BSC-01-v1",
          version: 1,
        },
        kpis: [
          {
            kpi: "total_revenue",
            value: "10,000",
          },
          {
            kpi: "total_revenue",
            value: "10,000",
          },
        ],
      },
      {
        plan: {
          plan_name: "Premium Plan",
          plan_id: "PRM-01",
          version_id: "PRM-01-v1",
          version: 1,
        },
        kpis: [
          {
            kpi: "total_revenue",
            value: "15,000",
          },
          {
            kpi: "total_revenue",
            value: "15,000",
          },
        ],
      },
    ],
    revenue_per_day_graph: [
      {
        date: "2022-03-01",
        revenue_per_plan: [
          {
            plan: {
              plan_name: "Basic Plan",
              plan_id: "BSC-01",
              version_id: "BSC-01-v1",
              version: 1,
            },
            revenue: "500",
          },
          {
            plan: {
              plan_name: "Premium Plan",
              plan_id: "PRM-01",
              version_id: "PRM-01-v1",
              version: 1,
            },
            revenue: "750",
          },
        ],
      },
      {
        date: "2022-03-02",
        revenue_per_plan: [
          {
            plan: {
              plan_name: "Basic Plan",
              plan_id: "BSC-01",
              version_id: "BSC-01-v1",
              version: 1,
            },
            revenue: "600",
          },
          {
            plan: {
              plan_name: "Premium Plan",
              plan_id: "PRM-01",
              version_id: "PRM-01-v1",
              version: 1,
            },
            revenue: "900",
          },
        ],
      },
    ],
    revenue_by_metric_graph: [
      {
        plan: {
          plan_name: "Basic Plan",
          plan_id: "BSC-01",
          version_id: "BSC-01-v1",
          version: 1,
        },
        by_metric: [
          {
            metric: {
              metric_id: "MT001",
              event_name: "Product View",
              metric_name: "Product Views",
            },
            revenue: "8,000",
          },
          {
            metric: {
              metric_id: "MT002",
              event_name: "Add to Cart",
              metric_name: "Add to Cart",
            },
            revenue: "2,000",
          },
        ],
      },
      {
        plan: {
          plan_name: "Premium Plan",
          plan_id: "PRM-01",
          version_id: "2342",
          version: 1,
        },
        by_metric: [
          {
            metric: {
              metric_id: "MT001",
              event_name: "Product View",
              metric_name: "Product Views",
            },
            revenue: "12,000",
          },
          {
            metric: {
              metric_id: "MT002",
              event_name: "Add to Cart",
              metric_name: "Add to Cart",
            },
            revenue: "3,000",
          },
        ],
      },
    ],
    top_customers: {
      top_customers_by_revenue: [
        {
          customer: {
            customer_name: "ABC Corp",
            email: "abc@example.com",
            customer_id: "CST001",
          },
          value: "5,000",
        },
        {
          customer: {
            customer_name: "XYZ Corp",
            email: "xyz@example.com",
            customer_id: "CST002",
          },
          value: "4,000",
        },
      ],
    },
  },
  analysis_id: "MAR2022-001",
};

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
  }: UseQueryResult<components["schemas"]["AnalysisDetail"]> = useQuery<
    components["schemas"]["AnalysisDetail"]
  >(["experiment_results", experimentId], () =>
    Experiments.getAnalysis(experimentId).then((res) => res)
  );

  const [selectedKPI, setSelectedKPI] = React.useState<string>();
  const [kpiOptions, setKpiOptions] = React.useState<
    { value: string; label: string }[]
  >([]);

  // const changeSubstitution = (value: string) => {
  //   const selectedSubstitution =
  //     experiment?.backtest_results.substitution_results.find(
  //       (substitution) => substitution.substitution_name === value
  //     );
  //   setSelectedSubstitution(selectedSubstitution);
  // };

  useEffect(() => {
    if (experiment && experiment.analysis_results.analysis_summary.length > 0) {
      //loop through analysis_summary and get all the kpi names into one array
      var newKPIOptions: { label: string; value: string }[] = [];
      for (
        let i = 0;
        i < experiment.analysis_results.analysis_summary.length;
        i++
      ) {
        console.log(
          experiment.analysis_results.analysis_summary[i].kpis[0].kpi
        );
        let kpiName =
          experiment.analysis_results.analysis_summary[i].kpis[0].kpi;
        if (
          !newKPIOptions.some((item) => Object.values(item).includes(kpiName))
        ) {
          newKPIOptions.push({ label: kpiName, value: kpiName });
        }
      }
      setKpiOptions(newKPIOptions);
      setSelectedKPI(newKPIOptions[0].value);
    }
    console.log(kpiOptions);
  }, [experiment]);

  // if (isLoading) {
  //   return (
  //     <div className="flex h-screen">
  //       <div className="m-auto">
  //         <LoadingSpinner />
  //       </div>
  //     </div>
  //   );
  // }

  return (
    <PageLayout
      title={experiment?.analysis_name}
      className="text-[24px] font-alliance "
      hasBackButton={true}
      aboveTitle
      mx={false}
      extra={<Button disabled={true}>Settings</Button>}
      backButton={
        <div>
          <Button
            onClick={() => navigate(-1)}
            type="primary"
            size="large"
            key="create-custom-plan"
            style={{
              background: "#F5F5F5",
              borderColor: "#F5F5F5",
            }}
          >
            <div className="flex items-center justify-between text-black">
              <div>&larr; Go back</div>
            </div>
          </Button>
        </div>
      }
    >
      {experiment === undefined || isLoading ? (
        <div className="min-h-[60%]">
          <LoadingSpinner />
        </div>
      ) : (
        <div className="">
          <div className="flex flex-wrap gap-18">
            {experiment.analysis_results.analysis_summary.map(
              (summary, index) => {
                return (
                  <div
                    key={index}
                    className=" rounded border-[#EAEAEB] px-10  bg-[#F9F9F9] flex-grow"
                  >
                    <div className=" mt-8">
                      <div className="">
                        <h2 className="font-semiBold text-xl text-black">
                          {summary.plan.plan_name}
                        </h2>
                      </div>

                      <div className="w-full h-[1.5px] my-8 bg-card-divider" />

                      <div className="grid grid-cols-4">
                        {summary.kpis.map((kpi, kpiIndex) => {
                          return (
                            <div
                              key={kpiIndex}
                              className="col-span-1 flex flex-col flex-start"
                            >
                              <div className="text-2xl font-semiBold">
                                {kpi.value}
                              </div>
                              <div className="text-sm  text-card-grey">
                                {kpi.kpi}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                      <div className=" text-sm my-8 flex align-middle">
                        Date Range:{" "}
                        <div className=" text-card-grey">
                          {experiment.start_date} -{experiment.end_date}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              }
            )}
          </div>

          <div className="mt-14 justify-between flex flex-row">
            <div className="text-base font-semiBold  text-black">Results</div>
            <Select
              onChange={(e) => {
                setSelectedKPI(e);
              }}
              value={selectedKPI}
            >
              {kpiOptions.map((kpiOption) => {
                return (
                  <option key={kpiOption.value} value={kpiOption.value}>
                    {kpiOption.label}
                  </option>
                );
              })}
            </Select>
          </div>

          {experiment && (
            <ExperimentDetails
              kpi={"Revenue"}
              data={experiment.analysis_results}
            />
          )}
        </div>
      )}
    </PageLayout>
  );
};

export default ExperimentResults;
