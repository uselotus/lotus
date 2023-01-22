import { Button, Form, Input, InputNumber } from "antd";
// @ts-ignore
import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient, UseQueryResult } from "react-query";
import { toast } from "react-toastify";
import { Credits, PricingUnits } from "../api/api";
import { CreateCreditType } from "../types/balance-adjustment";
import { useQuery } from "react-query";
import { CurrencyType } from "../types/pricing-unit-type";
import PricingUnitDropDown from "../components/PricingUnitDropDown";
// @ts-ignore
import dayjs from "dayjs";
import { DatePicker } from "antd";

type Params = {
  customerId: string;
};

const CreateCredit = ({ customerId, onSubmit }) => {
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const queryClient = useQueryClient();

  const { data, isLoading }: UseQueryResult<CurrencyType[]> = useQuery<
    CurrencyType[]
  >(["pricing_unit_list"], () =>
    PricingUnits.list().then((res) => {
      return res;
    })
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

  const disabledDate = (current) => {
    return current && current < dayjs().startOf("day");
  };

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
    <div className=" w-8/12 my-4">
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
          labelCol={{ span: 8 }}
          wrapperCol={{ span: 16 }}
          labelAlign="left"
        >
          <div className=" grid grid-cols-2 gap-4 p-4 border-2">
            <Form.Item
              label="Amount"
              name="amount"
              rules={[
                {
                  required: true,
                  message: "Please enter an amount",
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
            <Form.Item name="amount_paid" label="Amount Paid">
              <InputNumber precision={2} onChange={handleAmountPaidChange} />
            </Form.Item>
            <Form.Item
              name="amount_paid_currency"
              label="Currency"
              rules={[validateAmountPaidCurrency]}
            >
              <PricingUnitDropDown
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
            <div>
              {amount_paid > 0 && amount_paid !== null ? (
                <div className="warning-text mb-2 text-darkgold">
                  Warning: An invoice will be generated for the amount paid of{" "}
                  {amount_paid} {amount_paid_currency}.
                </div>
              ) : null}

              <Form.Item>
                <Button
                  type="primary"
                  htmlType="submit"
                  className="mr-4"
                  loading={mutation.isLoading}
                >
                  Submit
                </Button>
              </Form.Item>
            </div>
          </div>
        </Form>
      </Form.Provider>
    </div>
  );
};

export default CreateCredit;
