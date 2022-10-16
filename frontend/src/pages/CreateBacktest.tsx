import React, { FC, useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "react-query";
import { useNavigate } from "react-router-dom";
import { PlanType } from "../types/plan-type";
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
  const navigateUpdatePlan = () => {
    navigate("/plans/update");
  };
  const queryClient = useQueryClient();

  const [form] = Form.useForm();
  const [substitutions, setSubstitutions] = useState<Substitution[]>([]);
  const { currentPlan, replacementPlan } = usePlanState();
  const { setCurrentPlan, setReplacementPlan } = usePlanUpdater();
  const [replacePlanVisible, setReplacePlanVisible] = useState<boolean>(false);
  const [newPlanVisible, setNewPlanVisible] = useState<boolean>(false);
  const [startDate, setStartDate] = useState<string>();

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
        queryClient.invalidateQueries(["experiments_list"]);
        navigate("/experiments");
      },

      onError: (e) => {
        toast.error("Error creating backtest");
      },
    }
  );

  const runBacktest = () => {
    form.validateFields().then((values) => {
      const start_date = dayjs()
        .subtract(values.date_range, "month")
        .format("YYYY-MM-DD");
      console.log(start_date);
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
  };

  const openplanNewModal = () => {
    setNewPlanVisible(true);
  };
  const closeplanNewModal = () => {
    setNewPlanVisible(false);
  };

  const addCurrentPlanSlot = (plan_id: string) => {
    const current = plans?.find((plan) => plan.billing_plan_id === plan_id);
    setCurrentPlan(current);
  };

  const addReplacementPlanSlot = (plan_id: string) => {
    if (plans) {
      const replacement = plans.find(
        (plan) => plan.billing_plan_id === plan_id
      );
      setReplacementPlan(replacement);
    }
  };

  const generateRandomExperimentName = () => {
    const randomName = "experiment-" + Math.random().toString(36).substring(7);
    console.log(randomName);
    return randomName;
  };

  useEffect(() => {
    if (currentPlan && replacementPlan) {
      setSubstitutions([
        ...substitutions,
        {
          original_plans: [currentPlan.billing_plan_id],
          new_plan: replacementPlan.billing_plan_id,
        },
      ]);
      // setCurrentPlan(undefined);
      // setReplacementPlan(undefined);
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
        <Form
          form={form}
          onFinish={runBacktest}
          initialValues={{
            ["backtest_name"]: generateRandomExperimentName(),
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
            <Form.Item
              name="date_range"
              rules={[
                {
                  required: true,
                  message: "Select a date range",
                },
              ]}
            >
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
                  <Input />
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
                <div className="mt-4">
                  {currentPlan && (
                    <div className="flex rounded-lg text-xl bg-[#F7F8FD] py-3 px-2 justify-center">
                      <span className="font-bold">{currentPlan.name}</span>
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
                <div className="mt-4">
                  {replacementPlan && (
                    <div className="flex rounded-lg text-xl bg-[#F7F8FD] py-3 px-2 justify-center">
                      <span className="font-bold">{replacementPlan.name}</span>
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
            defaultValue={currentPlan?.billing_plan_id}
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
        onOk={() => {
          navigate("/backtest-plan");
        }}
        okText="Edit"
        closeIcon={<div></div>}
      >
        <div className="border-b border-gray-200 bg-[#F7F8FD] px-4 py-5 sm:px-6">
          <h3 className="mb-5">Choose New Plan To Backtest</h3>
          <h4 className="mb-5">
            Start From An Existing Plan, Then Edit The Differences
          </h4>
          <Select
            className="w-8/12"
            onChange={addReplacementPlanSlot}
            defaultValue={replacementPlan?.billing_plan_id}
          >
            {plans?.map((plan) => (
              <Select.Option value={plan.billing_plan_id}>
                {plan.name}
              </Select.Option>
            ))}
          </Select>
        </div>
      </Modal>
    </PageLayout>
  );
};

export default CreateBacktest;
