import React from "react";
import { Divider, Modal, Select, Input, Form, InputNumber } from "antd";
import { CurrencyType } from "../../types/pricing-unit-type";
import { components } from "../../gen-types";

interface Props {
  visible: boolean;
  onCancel: () => void;
  onAddRecurringCharges: (
    recurringCharge: components["schemas"]["PlanDetail"]["versions"][0]["recurring_charges"][number]
  ) => void;
  selectedCurrency: CurrencyType | null;
}

const INVOICING_INTERVAL_UNITS = [
  {
    label: "Daily",
    value: "day",
  },
  {
    label: "Weekly",
    value: "week",
  },
  {
    label: "Monthly",
    value: "month",
  },
  {
    label: "Yearly",
    value: "year",
  },
];

export default function RecurringChargeForm({
  visible,
  onCancel,
  onAddRecurringCharges,
  selectedCurrency,
}: Props) {
  const [form] = Form.useForm();

  console.log(selectedCurrency);

  return (
    <Modal
      visible={visible}
      title="Add Recurring Charge"
      okText="Add"
      okType="default"
      cancelText="Cancel"
      okButtonProps={{
        className: "bg-black text-white",
      }}
      onCancel={onCancel}
      onOk={async () => {
        try {
          await form.validateFields();
          form.submit();
        } catch (err) {
          // Do nothing
        }
      }}
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={{
          name: "",
          charge_timing: "in_advance",
          charge_behavior: "prorate",
          amount: 0.0,
          pricing_unit: selectedCurrency,
          invoicing_interval_unit: null,
          invoicing_interval_count: undefined,
          reset_interval_unit: null,
          reset_interval_count: undefined,
        }}
        name="recurring-charge-form"
        onFinish={(values) => {
          onAddRecurringCharges({
            name: values.name,
            charge_timing: values.charge_timing,
            charge_behavior: values.charge_behavior,
            amount: values.amount,
            pricing_unit: selectedCurrency!,
            invoicing_interval_unit: values.invoicing_interval_unit,
            invoicing_interval_count: values.invoicing_interval_count,
            reset_interval_unit: values.reset_interval_unit,
            reset_interval_count: values.reset_interval_count,
          });
        }}
      >
        <div className="grid grid-row-3">
          <div className="flex flex-col">
            <Form.Item name="name" label="Name" rules={[{ required: true }]}>
              <Input placeholder="Name" />
            </Form.Item>
          </div>

          <div className="flex flex-col">
            <Form.Item name="charge_timing" label="Charge Timing">
              <Select
                optionFilterProp="children"
                options={[
                  {
                    value: "in_advance",
                    label: "In Advance",
                  },
                  {
                    value: "in_arrears",
                    label: "In Arrears",
                  },
                ]}
              />
            </Form.Item>
          </div>

          <div className="flex flex-col">
            <Form.Item name="charge_behavior" label="Charge Behavior">
              <Select
                optionFilterProp="children"
                options={[
                  {
                    value: "prorate",
                    label: "Prorate",
                  },
                  {
                    value: "Full",
                    label: "full",
                  },
                ]}
              />
            </Form.Item>
          </div>

          <div className="flex flex-col">
            <Form.Item name="amount" label="Amount" wrapperCol={{ span: 24 }}>
              <InputNumber addonBefore={selectedCurrency?.symbol || null} />
            </Form.Item>
          </div>

          <Divider />

          <Input.Group>
            <div className="flex flex-row justify-between">
              <Form.Item
                name="invoicing_interval_unit"
                label="Invoice Interval Unit"
              >
                <Select options={INVOICING_INTERVAL_UNITS} />
              </Form.Item>

              <Form.Item
                name="invoicing_interval_count"
                label="Invoice Interval Count"
                wrapperCol={{ span: 12 }}
              >
                <InputNumber precision={0} />
              </Form.Item>
            </div>
          </Input.Group>

          <Input.Group>
            <div className="flex flex-row justify-between">
              <Form.Item name="reset_interval_unit" label="Reset Interval Unit">
                <Select options={INVOICING_INTERVAL_UNITS} />
              </Form.Item>

              <Form.Item
                name="reset_interval_count"
                label="Reset Interval Count"
                wrapperCol={{ span: 12 }}
              >
                <InputNumber precision={0} />
              </Form.Item>
            </div>
          </Input.Group>
        </div>
      </Form>
    </Modal>
  );
}
