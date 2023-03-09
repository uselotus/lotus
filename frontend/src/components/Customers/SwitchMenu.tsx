/* eslint-disable camelcase */
/* eslint-disable jsx-a11y/label-has-associated-control */
/* eslint-disable no-shadow */
import React from "react";
import { Form, Cascader, Input } from "antd";
import { DefaultOptionType } from "antd/lib/select";
import { SubscriptionType } from "../../types/subscription-type";
import { CascaderOptions } from "./CustomerSubscriptionView";

interface ChangeOption {
  value:
    | "change_subscription_plan"
    | "end_current_subscription_and_bill"
    | "end_current_subscription_dont_bill";
  label: string;
  disabled?: boolean;
}
interface PlanOption {
  value: string;
  label: string;
  children?: ChangeOption[];
  disabled?: boolean;
}
const filter = (inputValue: string, path: DefaultOptionType[]) =>
  (path[0].label as string).toLowerCase().indexOf(inputValue.toLowerCase()) >
  -1;

const displayRender = (labels: string[]) => labels[labels.length - 1];

const SwitchMenuComponent = ({
  plan_id,
  subscription_filters,
  subscriptions,
  plansWithSwitchOptions,
  setCascaderOptions,
  cascaderOptions,
}: {
  plan_id: string;
  subscription_filters: SubscriptionType["subscription_filters"];
  subscriptions: SubscriptionType[];
  plansWithSwitchOptions: (plan_id: string) => PlanOption[] | undefined;
  setCascaderOptions: (args: CascaderOptions) => void;
  cascaderOptions: CascaderOptions;
}) => (
  <div>
    <Form.Item>
      <label htmlFor="addon_id" className="mb-4 required">
        Current Plan
      </label>
      <Input
        className="!mt-2"
        placeholder={
          subscriptions.filter((el) => el.billing_plan.plan_id === plan_id)[0]
            .billing_plan.plan_name
        }
        disabled
      />
    </Form.Item>
    <Form.Item>
      <label htmlFor="addon_id" className="mb-4 required">
        New Plan
      </label>
      <div>
        <Cascader
          className="!w-[332px] !mt-2"
          options={plansWithSwitchOptions(plan_id)}
          onChange={(value) =>
            setCascaderOptions({
              value: value[0] as string,
              plan_id,
              subscriptionFilters: subscription_filters,
            })
          }
          value={[cascaderOptions?.value]}
          expandTrigger="hover"
          placeholder="Please select"
          showSearch={{ filter }}
          displayRender={displayRender}
          changeOnSelect
          style={{ width: "80%" }}
        />
      </div>
    </Form.Item>
  </div>
);

const SwitchMenu = React.memo(SwitchMenuComponent);

export default SwitchMenu;
