import { Button, Form, Input, InputNumber, DatePicker, Modal } from "antd";
import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  useMutation,
  useQueryClient,
  UseQueryResult,
  useQuery,
} from "@tanstack/react-query";
import { toast } from "react-toastify";
import dayjs from "dayjs";
import { Credits, PricingUnits } from "../api/api";
import { CreateCreditType } from "../types/balance-adjustment";
import { CurrencyType } from "../types/pricing-unit-type";
import PricingUnitDropDown from "../components/PricingUnitDropDown";

type Params = {
  customerId: string;
  onSubmit: () => void;
  visible: boolean;
  onCancel: () => void;
};

function CreateCredit({ customerId, visible, onCancel, onSubmit }: Params) {
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const queryClient = useQueryClient();

  useQuery<CurrencyType[]>(["pricing_unit_list"], () =>
    PricingUnits.list().then((res) => res)
  );
  const [amount_paid, setAmountPaid] = useState(
    form.getFieldValue("amount_paid")
  );
  const [amount_paid_currency, setAmountPaidCurrency] = useState(
    form.getFieldValue("amount_paid_currency")
  );

  const handleAmountPaidChange = (value) => {
    setAmountPaid(value);
  };

  const handleAmountPaidCurrencyChange = (value) => {
    setAmountPaidCurrency(value);
  };

  const disabledDate = (current) => current && current < dayjs().startOf("day");

  const mutation = useMutation(
    (post: CreateCreditType) => Credits.createCredit(post),
    {
      onSuccess: () => {
        toast.success("Successfully created Credit", {
          position: toast.POSITION.TOP_CENTER,
        });
        form.resetFields();
        queryClient.invalidateQueries(["customer_list"]);
        queryClient.invalidateQueries(["balance_adjustments"]);
        queryClient.invalidateQueries(["customer_detail", customerId]);
      },
      onError: () => {
        toast.error("Failed to create Credit", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
    }
  );

  const submit = () => {
    form
      .validateFields()
      .then((values) => {
        mutation.mutate({
          customer_id: customerId,
          amount: values.amount,
          description: values.description,
          currency_code: values.pricing_unit_code,
          effective_at: values.effective_at,
          expires_at: values.expires_at,
          amount_paid: values.amount_paid,
          amount_paid_currency_code: values.amount_paid_currency,
        });
        onSubmit();
      })
      .catch((info) => {});
  };

  const validateAmountPaidCurrency = () => ({
    validator(rule, value, callback) {
      const { amount_paid } = form.getFieldsValue();
      if (amount_paid !== null && amount_paid > 0 && !value) {
        callback("Please select an amount paid currency");
      } else {
        callback();
      }
    },
  });

  return (
    <Modal
      width={1000}
      destroyOnClose={true}
      title="Create Credit"
      visible={visible}
      footer={[
        <Button key="back" onClick={onCancel}>
          Cancel
        </Button>,
        <Button key="submit" type="primary" onClick={submit}>
          Submit
        </Button>,
      ]}
    >
      <Form.Provider>
        <Form
          form={form}
          name="create_credit"
          initialValues={{
            amount: null,
            description: "",
            pricing_unit_code: null,
            effective_at: dayjs(Date.now()),
            expires_at: null,
          }}
          onFinish={submit}
          autoComplete="off"
          labelWrap={true}
        >
          <div className=" grid grid-cols-2 gap-4 p-4">
            <Form.Item
              label="Amount Granted"
              name="amount"
              rules={[
                {
                  required: true,
                  message: "Please enter an amount",
                },
                {
                  validator(rule, value, callback) {
                    if (value <= 0) {
                      callback("Value must be greater than 0");
                    } else {
                      callback();
                    }
                  },
                },
              ]}
            >
              <InputNumber defaultValue={0} precision={2} />
            </Form.Item>
            <Form.Item
              rules={[{ required: true, message: "Please Select a currency" }]}
              name="pricing_unit_code"
              label="Currency"
            >
              <PricingUnitDropDown
                setCurrentCurrency={(value) =>
                  form.setFieldValue("pricing_unit_code", value)
                }
                setCurrentSymbol={() => null}
              />
            </Form.Item>
            <Form.Item
              name="amount_paid"
              label="Amount Paid"
              rules={[
                {
                  validator(rule, value, callback) {
                    if (value && value < 0) {
                      callback("Value must be greater than 0");
                    } else {
                      callback();
                    }
                  },
                },
              ]}
            >
              <InputNumber precision={2} onChange={handleAmountPaidChange} />
            </Form.Item>
            <Form.Item
              name="amount_paid_currency"
              label="Paid Currency"
              rules={[validateAmountPaidCurrency]}
            >
              <PricingUnitDropDown
                disabled={amount_paid === null || amount_paid === 0}
                setCurrentCurrency={(value) => {
                  form.setFieldValue("amount_paid_currency", value);
                  handleAmountPaidCurrencyChange(value);
                }}
                setCurrentSymbol={() => null}
              />
            </Form.Item>
            <Form.Item
              valuePropName="date"
              rules={[{ required: true, message: "Please Select a date" }]}
              name="effective_at"
              label="Effective At"
            >
              <DatePicker
                defaultValue={dayjs(Date.now())}
                disabledDate={disabledDate}
                onChange={(data) =>
                  form.setFieldValue("effective_at", dayjs(data))
                }
              />
            </Form.Item>
            <Form.Item
              valuePropName="date"
              name="expires_at"
              label="Expires At"
            >
              <DatePicker
                disabledDate={disabledDate}
                onChange={(data) =>
                  form.setFieldValue("expires_at", dayjs(data))
                }
              />
            </Form.Item>
            <Form.Item
              label="Description"
              name="description"
              className="col-span-2"
            >
              <Input type="textarea" placeholder="Description for adjustment" />
            </Form.Item>
          </div>
          <div>
            {amount_paid > 0 && amount_paid !== null ? (
              <div className="warning-text mb-2 text-darkgold">
                Warning: An invoice will be generated for the amount paid of{" "}
                {amount_paid} {amount_paid_currency}.
              </div>
            ) : null}
          </div>
        </Form>
      </Form.Provider>
    </Modal>
  );
}

export default CreateCredit;
