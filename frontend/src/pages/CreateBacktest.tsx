import React, { FC, useState } from "react";
import { useQuery, useMutation } from "react-query";
import { useNavigate } from "react-router-dom";
import { PlanType } from "../types/plan-type";
import { Plan } from "../api/api";
import { Form, Button, Input, Radio, Tag } from "antd";
import { PageLayout } from "../components/base/PageLayout";
import { CreateBacktestType, Substitution } from "../types/experiment-type";
import { Backtests } from "../api/api";
import { toast } from "react-toastify";

const CreateBacktest: FC = () => {
  const navigate = useNavigate();
  const navigateUpdatePlan = () => {
    navigate("/plans/update");
  };
  const [form] = Form.useForm();
  const [substitutions, setSubstitutions] = useState<Substitution[]>([]);

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
        <Form>
          <div className="border-b border-gray-200 bg-white px-4 py-5 sm:px-6">
            <h2>Test Type</h2>
            <Radio.Group defaultValue="a" buttonStyle="solid">
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
            <h3>Date Range</h3>
            <Form.Item name="date_range">
              <Radio.Group
                defaultValue="a"
                buttonStyle="solid"
                className=" space-x-2"
              >
                <Radio.Button value={1}>1 Month</Radio.Button>
                <Radio.Button value={3}>3 Months</Radio.Button>
                <Radio.Button value={6}>6 Months</Radio.Button>
                <Radio.Button value={12}>1 Year</Radio.Button>
              </Radio.Group>
            </Form.Item>
          </div>
          <div className="border-b border-gray-200 bg-white px-4 py-5 sm:px-6">
            <h3>Test Plan Variations</h3>
          </div>

          <div className="border-b border-gray-200 bg-white px-4 py-5 sm:px-6">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <h3>Experiment Name</h3>
                <Form.Item name={"backtest_name"}>
                  <Input />
                </Form.Item>
              </div>
              <div>
                <h3>KPIs</h3>
                <div className="ml-10 ">
                  {" "}
                  <Radio.Button value={true}>Total Revenue</Radio.Button>
                </div>
              </div>
            </div>
          </div>
        </Form>
      </div>
    </PageLayout>
  );
};

export default CreateBacktest;
