import React, { useState } from "react";
import { Radio } from "antd";
import { CancelSubscriptionBody } from "../../types/subscription-type";

type usageBehaviorType = CancelSubscriptionBody["usage_behavior"];
type recurringBehaviorType = CancelSubscriptionBody["flat_fee_behavior"];
type invoiceBehaviorType = CancelSubscriptionBody["invoicing_behavior"];

const CancelMenuComponent = ({
  setUsageBehavior,
  setRecurringBehavior,
  setInvoiceBehavior,
  recurringBehavior,
  usageBehavior,
  invoiceBehavior,
}: {
  setUsageBehavior: (e: usageBehaviorType) => void;
  setRecurringBehavior: (e: recurringBehaviorType) => void;
  setInvoiceBehavior: (e: invoiceBehaviorType) => void;
  recurringBehavior: recurringBehaviorType;

  usageBehavior: usageBehaviorType;
  invoiceBehavior: invoiceBehaviorType;
}) => (
  <div className=" space-y-10">
    <p className="text-base Inter">
      If you cancel a plan the customer will lose it permanently, and you
      won&apos;t be able to recover it.
    </p>

    <h3>Recurring (Pre-paid) Charge Behavior</h3>
    <Radio.Group
      onChange={(e) => setRecurringBehavior(e.target.value)}
      buttonStyle="solid"
      style={{ width: "100%" }}
      value={recurringBehavior}
    >
      <div className="flex flex-row items-center gap-4">
        <Radio.Button value="refund">Refund As Credit</Radio.Button>
        <Radio.Button value="charge_prorated">Prorated Amount</Radio.Button>
        <Radio.Button value="charge_full">Full Amount</Radio.Button>
      </div>
    </Radio.Group>
    <h3 className="mt-10">Usage Behavior</h3>

    <Radio.Group
      onChange={(e) => {
        console.log(e.target.value); // check if value is being captured correctly
        setUsageBehavior(e.target.value);
      }}
      buttonStyle="solid"
      style={{ width: "100%" }}
      value={usageBehavior}
    >
      <div className="flex flex-row items-center gap-4">
        <Radio.Button value="bill_full">Bill Usage</Radio.Button>

        <Radio.Button value="bill_none">Don&apos;t Bill</Radio.Button>
      </div>
    </Radio.Group>
    <h3 className="mt-10">How to Invoice</h3>

    <Radio.Group
      onChange={(e) => setInvoiceBehavior(e.target.value)}
      buttonStyle="solid"
      style={{ width: "100%" }}
      value={invoiceBehavior}
    >
      <div className="flex flex-row items-center gap-4">
        <Radio.Button value="add_to_next_invoice">
          Add to next invoice
        </Radio.Button>

        <Radio.Button value="invoice_now">Invoice now</Radio.Button>
      </div>
    </Radio.Group>
  </div>
);
const CancelMenu = React.memo(CancelMenuComponent);

export default CancelMenu;
