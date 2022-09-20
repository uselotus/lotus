import React, { FC, useEffect, useState } from "react";
import { PlanType } from "../../types/plan-type";
import { Card, List, Form, Select, Button } from "antd";

interface Props {
  subscriptions: string[];
  plans: PlanType[] | undefined;
  onChange: (subscription: any) => void;
}

const SubscriptionView: FC<Props> = ({ subscriptions, plans, onChange }) => {
  const [selectedPlan, setSelectedPlan] = useState<string>();
  const [idtoPlan, setIDtoPlan] = useState<{ [key: string]: PlanType }>({});
  const [planList, setPlanList] =
    useState<{ label: string; value: string }[]>();

  const selectPlan = (plan_id: string) => {
    console.log(plan_id, "22");

    setSelectedPlan(plan_id);
  };

  useEffect(() => {
    if (plans !== undefined) {
      const planMap = plans.reduce((acc, plan) => {
        acc[plan.billing_plan_id] = plan;
        return acc;
      }, {} as { [key: number]: PlanType });
      setIDtoPlan(planMap);
      const newplanList: { label: string; value: string }[] = plans.map(
        (plan) => {
          return { label: plan.name, value: plan.billing_plan_id };
        }
      );
      console.log(newplanList);
      setPlanList(newplanList);
    }
  }, [plans]);

  const handleSubmit = () => {
    console.log(selectedPlan);
    if (selectedPlan) {
      onChange(idtoPlan[selectedPlan]);
    }
  };

  if (subscriptions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center">
        <h3 className="text-xl font-main m-3">No Subscription</h3>
        <p className="font-bold">Please attatch a Plan</p>
        <div className=" h-3/6">
          <Form onFinish={handleSubmit} name="create_subscription">
            <Form.Item name="plan">
              <Select
                showSearch
                placeholder="Select a plan"
                onChange={selectPlan}
                options={planList}
                optionLabelProp="label"
              >
                {" "}
              </Select>
            </Form.Item>
            <Form.Item>
              <Button htmlType="submit"> Attatch Plan</Button>
            </Form.Item>
          </Form>
        </div>
      </div>
    );
  }
  return (
    <List>
      {subscriptions.map((subscription) => (
        <List.Item>
          <Card>{subscription}</Card>
        </List.Item>
      ))}
    </List>
  );
};

export default SubscriptionView;
