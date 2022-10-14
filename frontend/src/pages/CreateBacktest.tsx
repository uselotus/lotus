import React, { FC, useEffect, useState } from "react";
import { useQuery, useMutation } from "react-query";
import { useNavigate, Link } from "react-router-dom";
import { PlanType } from "../types/plan-type";
import { Plan } from "../api/api";
import { Form, Button, Input, Radio, Select, Modal } from "antd";
import { PageLayout } from "../components/base/PageLayout";
import { CreateBacktestType, Substitution } from "../types/experiment-type";
import { Backtests } from "../api/api";
import { toast } from "react-toastify";

interface PlanRepType {
  plan_id: string;
  plan_name: string;
}

const CreateBacktest: FC = () => {
  const navigate = useNavigate();
  const navigateUpdatePlan = () => {
    navigate("/plans/update");
  };
  const [form] = Form.useForm();
  const [substitutions, setSubstitutions] = useState<Substitution[]>([]);
  const [replacePlanVisible, setReplacePlanVisible] = useState<boolean>(false);
  const [newPlanVisible, setNewPlanVisible] = useState<boolean>(false);
  const [startDate, setStartDate] = useState<string>("");
  const [endDate, setEndDate] = useState<string>("");
  const [currentPlan, setCurrentPlan] = useState<PlanRepType>();
  const [replacementPlan, setReplacementPlan] = useState<PlanRepType>();

  const {
    data: plans,
    isLoading,
    isError,
  } = useQuery<PlanType[]>(["plan_list"], () =>
    Plan.getPlans().then((res) => {
      return res;
    })
  );

  const mutation = useMutation(
    (post: CreateBacktestType) => Backtests.createBacktest(post),
    {
      onSuccess: () => {
        toast.success("Started Backtest");
        navigate("/experiments");
      },

      onError: (e) => {
        toast.error("Error creating backtest");
      },
    }
  );

  const runBacktest = () => {
    form.validateFields().then((values) => {
      const post: CreateBacktestType = {
        backtest_name: values.backtest_name,
        start_time: values.start_time,
        end_time: values.end_time,
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
  };

  const openplanNewModal = () => {
    setNewPlanVisible(true);
  };
  const closeplanNewModal = () => {
    setNewPlanVisible(false);
  };

  const addCurrentPlanSlot = (plan_id: string, name: string) => {
    setCurrentPlan({ plan_id: plan_id, plan_name: name });
    closeplanCurrentModal();
  };

  const addReplacementPlanSlot = (plan_id: string, name: string) => {
    setReplacementPlan({ plan_id: plan_id, plan_name: name });
    closeplanNewModal();
  };

  const generateRandomExperimentName = () => {
    const randomName = "experiment-" + Math.random().toString(36).substring(7);
    console.log(randomName);
    return randomName;
  };

  useEffect(() => {
    if (currentPlan !== undefined && replacementPlan !== undefined) {
      setSubstitutions([
        ...substitutions,
        {
          old_plans: [currentPlan.plan_id],
          new_plan: replacementPlan.plan_id,
        },
      ]);
      setCurrentPlan(undefined);
      setReplacementPlan(undefined);
    }
  }, [currentPlan, replacementPlan]);

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
        <Form form={form} onFinish={runBacktest}>
          <div className="border-b border-gray-200 bg-white px-4 py-5 sm:px-6">
            <h3 className=" font-bold">Test Type</h3>
            <Radio.Group
              defaultValue="backtest"
              buttonStyle="solid"
              value="backtest"
            >
              <Radio.Button value="backtest">Backtest</Radio.Button>
              <Radio.Button value="forcast" disabled={true}>
                Forcast
              </Radio.Button>
              <Radio.Button value="deployment" disabled={true}>
                Deployed Test
              </Radio.Button>
            </Radio.Group>
          </div>

          <div className="border-b border-gray-200 bg-white px-4 py-5 sm:px-6">
            <h3 className=" font-bold">Date Range</h3>
            <Form.Item name="date_range">
              <Radio.Group buttonStyle="solid">
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
                  <Input defaultValue={generateRandomExperimentName()} />
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
                  {currentPlan !== undefined && (
                    <div>
                      <h3 className=" font-bold">{currentPlan.plan_name}</h3>
                    </div>
                  )}
                </div>
              </div>

              <div>
                <h2 className=" text-sm">to</h2>
              </div>

              <div className="col-span-1">
                <Button onClick={openplanNewModal}>
                  Choose Plans To Replace
                </Button>
                <div>
                  {replacementPlan !== undefined && (
                    <div>
                      <h3 className=" font-bold">
                        {replacementPlan.plan_name}
                      </h3>
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
        closeIcon={null}
      >
        <div className="border-b border-gray-200 bg-[#F7F8FD] px-4 py-5 sm:px-6">
          <h3 className="mb-5">Choose An Existing Plan To Replace</h3>
          <Select
            onChange={(value) => {
              addCurrentPlanSlot(
                value,
                plans.find((x) => x.billing_plan_id === value).name
              );
            }}
          >
            {plans?.map((plan) => (
              <Select.Option value={plan.billing_plan_id}>
                {plan.name}
              </Select.Option>
            ))}
          </Select>
        </div>
      </Modal>
      <Modal
        visible={newPlanVisible}
        onCancel={closeplanNewModal}
        onOk={closeplanNewModal}
        closeIcon={null}
      >
        <div className="border-b border-gray-200 bg-[#F7F8FD] px-4 py-5 sm:px-6">
          <h3 className="mb-5">Choose New Plan To Backtest</h3>
          <h4 className="mb-5">
            Start From An Existing Plan, Then Edit The Differences
          </h4>
          <Select>
            {plans?.map((plan) => (
              <Select.Option value={plan.billing_plan_id}>
                <Link
                  to="/backtest-plan"
                  state={{
                    plan: {
                      plan: plan,
                      //   onSubstitutionChange: addReplacementPlanSlot,
                    },
                  }}
                >
                  {plan.name}
                </Link>
              </Select.Option>
            ))}
          </Select>
        </div>
      </Modal>
    </PageLayout>
  );
};

export default CreateBacktest;
