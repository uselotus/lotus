import React, { FC, useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "react-query";
import { useNavigate } from "react-router-dom";
import { PlanDetailType, PlanType, PlanVersionType } from "../types/plan-type";
import { Plan } from "../api/api";
import { Form, Button, Input, Radio, Select, Modal } from "antd";
import { PageLayout } from "../components/base/PageLayout";
import { CreateBacktestType, Substitution } from "../types/experiment-type";
import { Backtests } from "../api/api";
import { toast } from "react-toastify";
import { usePlanState, usePlanUpdater } from "../context/PlanContext";
import dayjs from "dayjs";
interface PlanRepType {
  plan_id: string;
  plan_name: string;
}

const CreateBacktest: FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [form] = Form.useForm();
  const [substitutions, setSubstitutions] = useState<Substitution[]>([]);
  const {
    currentPlan,
    replacementPlan,
    currentPlanVersion,
    replacementPlanVersion,
    experimentName,
    dateRange,
  } = usePlanState();
  const [currentPlanModal, setCurrentPlanModal] = useState<PlanType>();
  const [replacementPlanModal, setReplacementPlanModal] =
    useState<PlanVersionType>();
  const {
    setCurrentPlan,
    setReplacementPlan,
    setCurrentPlanVersion,
    setReplacementPlanVersion,
    setExperimentName,
    setDateRange,
  } = usePlanUpdater();
  const [replacePlanVisible, setReplacePlanVisible] = useState<boolean>(false);
  const [newPlanVisible, setNewPlanVisible] = useState<boolean>(false);

  //temp

  const {
    data: plans,
    isLoading,
    isError,
  } = useQuery<PlanType[]>(["plan_list"], () =>
    Plan.getPlans().then((res) => {
      return res;
    })
  );

  const {
    data: planDetails,
    isLoading: planDetailsLoading,
    isError: planDetailsError,
  } = useQuery<PlanDetailType>(["plan_details", currentPlan?.plan_id], () =>
    Plan.getPlan(currentPlan?.plan_id || "11").then((res) => {
      return res;
    })
  );

  const mutation = useMutation(
    (post: CreateBacktestType) => Backtests.createBacktest(post),
    {
      onSuccess: () => {
        toast.success("Started Backtest");
        queryClient.invalidateQueries(["experiments_list"]);
        navigate("/experiments");
      },
      onError: (e) => {
        toast.error("Error creating backtest");
      },
    }
  );

  const runBacktest = () => {
    var singlesubscription: Substitution[];
    if (currentPlan && replacementPlan) {
      submitSubstitution();
    } else if (substitutions.length === 0) {
      toast.error("Please select a few plans");
      return null;
    }
    form.validateFields().then((values) => {
      const start_date = dayjs()
        .subtract(values.date_range, "month")
        .format("YYYY-MM-DD");
      const post: CreateBacktestType = {
        backtest_name: values.backtest_name,
        start_date: start_date,
        end_date: dayjs().format("YYYY-MM-DD"),
        kpis: ["total_revenue"],
        substitutions: substitutions,
      };

      mutation.mutate(post);
    });
  };

  const openplanCurrentModal = () => {
    setReplacePlanVisible(true);
  };
  const closeplanCurrentModal = () => {
    setReplacePlanVisible(false);
    submitSubstitution();
  };

  const openplanNewModal = () => {
    setNewPlanVisible(true);
  };
  const closeplanNewModal = () => {
    setNewPlanVisible(false);
    submitSubstitution();
  };

  useEffect(() => {
    submitSubstitution();
  }, []);

  // const changeCurrentPlanModal = (plan_id: string) => {
  //   const current = plans?.find((plan) => plan.plan_id === plan_id);

  //   setCurrentPlanModal(current);
  // };

  // const changeReplacementPlanModal = (plan_id: string) => {
  //   const replacement = plans?.find((plan) => plan.plan_id === plan_id);
  //   setReplacementPlanModal(replacement);
  // };

  const addCurrentPlanSlot = (plan_id: string) => {
    const current = plans?.find((plan) => plan.plan_id === plan_id);
    if (current) {
      console.log(current);
      setCurrentPlan(current);
      queryClient.invalidateQueries(["plan_details"]);
    }
  };

  const addReplacementPlanSlot = (plan_id: string) => {
    if (plans) {
      const replacement = plans.find((plan) => plan.plan_id === plan_id);
      if (replacement) {
        setReplacementPlan(replacement);
      }
    }
  };

  const addCurrentPlanVersion = (version_id: string) => {
    if (planDetails) {
      const current = planDetails.versions.find(
        (version) => version.version_id === version_id
      );
      if (current) {
        setCurrentPlanVersion(current);
      }
    }
  };

  const addReplacementPlanVersion = (version_id: string) => {
    if (planDetails) {
      const replacement = planDetails.versions.find(
        (version) => version.version_id === version_id
      );
      if (replacement) {
        setReplacementPlanVersion(replacement);
      }
    }
  };

  const submitSubstitution = () => {
    if (
      currentPlan &&
      replacementPlan &&
      currentPlanVersion &&
      replacementPlanVersion
    ) {
      setSubstitutions([
        ...substitutions,
        {
          original_plans: [currentPlanVersion?.version_id],
          new_plan: replacementPlanVersion?.version_id,
          new_plan_name: replacementPlan.plan_name,
          original_plan_names: [currentPlan.plan_name],
        },
      ]);
      setCurrentPlan(null);
      setReplacementPlan(null);
      setCurrentPlanVersion(null);
      setReplacementPlanVersion(null);
    }
  };

  return (
    <PageLayout
      title="New Experiment"
      extra={[
        <Button
          onClick={() => {
            form.submit();
          }}
          className="bg-black text-white justify-self-end"
          size="large"
          key={"update-plan"}
        >
          Run Experiment
        </Button>,
      ]}
    >
      <div className="space-y-8 divide-y divide-gray-200 w-md">
        <Form
          form={form}
          onFinish={() => {
            runBacktest();
          }}
          initialValues={{
            ["backtest_name"]: experimentName,
            ["date_range"]: dateRange,
          }}
        >
          <div className="border-b border-gray-200 bg-white px-4 py-5 sm:px-6">
            <h3 className=" font-bold">Test Type</h3>
            <Radio.Group
              defaultValue="backtest"
              buttonStyle="solid"
              value="backtest"
            >
              <Radio.Button value="backtest">Backtest</Radio.Button>
              <Radio.Button value="forecast" disabled={true}>
                Forecast
              </Radio.Button>
              <Radio.Button value="deployment" disabled={true}>
                Deployed Test
              </Radio.Button>
            </Radio.Group>
          </div>

          <div className="border-b border-gray-200 bg-white px-4 py-5 sm:px-6">
            <h3 className=" font-bold">Date Range</h3>
            <Form.Item
              name="date_range"
              rules={[
                {
                  required: true,
                  message: "Select a date range",
                },
              ]}
            >
              <Radio.Group
                buttonStyle="solid"
                onChange={(e) => {
                  setDateRange(e.target.value);
                }}
              >
                <Radio.Button value={1}>1 Month</Radio.Button>
                <Radio.Button value={3}>3 Months</Radio.Button>
                <Radio.Button value={6}>6 Months</Radio.Button>
                <Radio.Button value={12}>1 Year</Radio.Button>
              </Radio.Group>
            </Form.Item>
          </div>
          <div className="border-b border-gray-200 bg-white px-4 py-5 sm:px-6">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <h3 className=" font-bold">Experiment Name</h3>
                <Form.Item
                  name="backtest_name"
                  rules={[
                    {
                      required: true,
                      message: "Input an experiment name",
                    },
                  ]}
                >
                  <Input
                    onChange={(e) => {
                      setExperimentName(e.target.value);
                    }}
                  />
                </Form.Item>
              </div>
              <div>
                <h3 className=" font-bold">KPIs</h3>
                <div className="ml-10 ">
                  {" "}
                  <Radio.Button value={true}>Total Revenue</Radio.Button>
                </div>
              </div>
            </div>
          </div>
          <div className="border-b border-gray-200 bg-white px-4 py-5 sm:px-6">
            <h3 className=" font-bold">Test Plan Variations</h3>
            <div className="grid grid-cols-3 mt-6 mb-3 justify-items-center">
              <div className="col-span-1">
                <Button>
                  <a onClick={openplanCurrentModal}>Choose Plans To Replace</a>
                </Button>
                <div>
                  {substitutions.map((substitution, index) => {
                    return (
                      <div key={index}>
                        <p>
                          <div className="flex rounded-lg text-xl bg-[#FAFAFA] py-3 px-2 justify-center">
                            <span className="font-bold">
                              {substitution.original_plan_names[0]}
                            </span>
                          </div>
                        </p>
                      </div>
                    );
                  })}
                </div>
                <div className="mt-4">
                  {currentPlan && currentPlanVersion && (
                    <div className="flex flex-col rounded-lg text-xl bg-[#FAFAFA] py-3 px-2 items-center">
                      <p>Plan</p>
                      <span className="font-bold">
                        {currentPlan.plan_name}: v{currentPlanVersion?.version}
                      </span>
                    </div>
                  )}
                </div>
              </div>

              <div>
                <h2 className=" text-sm">to</h2>
              </div>

              <div className="col-span-1">
                <Button onClick={openplanNewModal}>
                  Create Experiment Plan
                </Button>
                <div>
                  {substitutions.map((substitution, index) => {
                    return (
                      <div key={index}>
                        <p>
                          <div className="flex rounded-lg text-xl bg-[#F7F8FD] py-3 px-2 justify-center">
                            <span className="font-bold">
                              {substitution.new_plan_name}
                            </span>
                          </div>
                        </p>
                      </div>
                    );
                  })}
                </div>
                <div className="mt-4">
                  {replacementPlan && replacementPlanVersion && (
                    <div className="flex flex-col rounded-lg text-xl bg-[#FAFAFA] py-3 px-2 items-center">
                      <p>Plan</p>
                      <span className="font-bold">
                        {replacementPlan.plan_name}: v
                        {replacementPlanVersion?.version}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </div>
            <div className="grid justify-items-center">
              <Button className=" max-w-md">+</Button>
            </div>
          </div>
        </Form>
      </div>
      <Modal
        visible={replacePlanVisible}
        onCancel={closeplanCurrentModal}
        onOk={closeplanCurrentModal}
        closeIcon={<div></div>}
      >
        <div className="border-b border-gray-200 bg-[#F7F8FD] px-4 py-5 sm:px-6">
          <h3 className="mb-5">Choose An Existing Plan To Replace</h3>
          <Select
            onChange={addCurrentPlanSlot}
            className="w-8/12"
            defaultValue={currentPlan?.plan_name}
          >
            {plans?.map((plan) => (
              <Select.Option value={plan.plan_id}>
                {plan.plan_name}
              </Select.Option>
            ))}
          </Select>
          <div className="my-10">
            {planDetails !== undefined && (
              <Select onChange={addCurrentPlanVersion} className="w-8/12">
                {planDetails?.versions.map((version) => (
                  <Select.Option value={version.version_id}>
                    {version.version}
                  </Select.Option>
                ))}
              </Select>
            )}
          </div>
        </div>
      </Modal>
      <Modal
        visible={newPlanVisible}
        onCancel={closeplanNewModal}
        onOk={() => {
          navigate("/backtest-plan");
        }}
        footer={[
          <Button key="back" onClick={closeplanNewModal}>
            Cancel
          </Button>,
          <Button
            key="submit"
            type="primary"
            onClick={() => {
              navigate("/backtest-plan/" + replacementPlan?.plan_id);
            }}
          >
            Edit
          </Button>,
          <Button key="link" type="primary" onClick={closeplanNewModal}>
            Use
          </Button>,
        ]}
        closeIcon={<div></div>}
      >
        <div className="border-b border-gray-200 bg-[#F7F8FD] px-4 py-5 sm:px-6">
          <h3 className="mb-5">Choose New Plan To Backtest</h3>
          <h4 className="mb-5">
            Start From An Existing Plan, Then Edit The Differences
          </h4>
          <Select
            className="w-8/12 mb-5"
            onChange={addReplacementPlanSlot}
            defaultValue={replacementPlan?.plan_name}
          >
            {plans?.map((plan) => (
              <Select.Option value={plan.plan_id}>
                {plan.plan_name}
              </Select.Option>
            ))}
          </Select>
          <div className="my-10">
            {planDetails !== undefined && (
              <Select onChange={addReplacementPlanVersion} className="w-8/12">
                {planDetails?.versions.map((version) => (
                  <Select.Option value={version.version_id}>
                    {version.version}
                  </Select.Option>
                ))}
              </Select>
            )}
          </div>
        </div>
      </Modal>
    </PageLayout>
  );
};

export default CreateBacktest;
