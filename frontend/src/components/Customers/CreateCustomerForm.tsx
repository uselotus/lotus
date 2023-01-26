import { Modal, Form, Input, Select } from "antd";
// @ts-ignore
import React from "react";
import PricingUnitDropDown from "../PricingUnitDropDown";
import { PaymentProcessorIntegration } from "../../api/api";
import { PaymentProcessorStatusType } from "../../types/payment-processor-type";
import { useQuery } from "react-query";

export interface CreateCustomerState {
  name: string;
  customer_id: string;
  title: string;
  subscriptions: string[];
  total_amount_due: number;
  email: string;
  payment_provider?: string;
  payment_provider_id?: string;
  default_currency_code?: string;
}

const CreateCustomerForm = (props: {
  visible: boolean;
  onSave: (state: CreateCustomerState) => void;
  onCancel: () => void;
}) => {
  const [form] = Form.useForm();
  const [paymentProviders, setPaymentProviders] = React.useState<string[]>([]);

  const { data, isLoading } = useQuery<PaymentProcessorStatusType[]>(
    ["payment_processor_integration_list"],
    () => PaymentProcessorIntegration.getPaymentProcessorConnectionStatus(),
    {
      onSuccess: (data) => {
        //set payment provider name in paymentproviders list if connected is true
        const connectedProviders = data
          .filter((item) => item.connected)
          .map((item) => item.payment_provider_name);
        setPaymentProviders(connectedProviders);
      },
    }
  );
  return (
    <Modal
      visible={props.visible}
      title="Create a Customer"
      okText="Create"
      okType="default"
      okButtonProps={{
        id: "Create-customer-button",
      }}
      cancelText="Cancel"
      onCancel={props.onCancel}
      onOk={() => {
        form
          .validateFields()
          .then((values) => {
            form.resetFields();
            props.onSave(values);
          })
          .catch((info) => {});
      }}
    >
      <Form form={form} layout="vertical" name="customer_form">
        <Form.Item
          name="email"
          label="Email"
          rules={[
            {
              required: true,
              type: "email",
              message: "Please input the email of the customer",
            },
          ]}
        >
          <Input id="customer-email" />
        </Form.Item>
        <Form.Item
          name="customer_id"
          label="Customer ID"
          rules={[
            {
              required: true,
              message: "Unique customer_id is required",
            },
          ]}
        >
          <Input id="customer-id" />
        </Form.Item>
        <Form.Item name="name" label="Name">
          <Input id="customer-name" />
        </Form.Item>

        <div className="grid grid-cols-6 items-center gap-4">
          {paymentProviders.length > 0 && (
            <Form.Item
              className="col-span-2"
              name="payment_provider"
              label="Payment Provider"
            >
              <Select>
                {paymentProviders.map((provider) => (
                  <Select.Option key={provider} value={provider}>
                    {provider}
                  </Select.Option>
                ))}
              </Select>
            </Form.Item>
          )}

          {paymentProviders.length > 0 && (
            <Form.Item
              className="col-span-4"
              name="payment_provider_id"
              label="Payment Provider ID"
            >
              <Input />
            </Form.Item>
          )}

          <Form.Item
            className="col-span-4"
            name="default_currency_code"
            label="Default currency"
          >
            <PricingUnitDropDown
              setCurrentCurrency={(value) =>
                form.setFieldValue("default_currency_code", value)
              }
            />
          </Form.Item>
        </div>
      </Form>
    </Modal>
  );
};

export default CreateCustomerForm;
