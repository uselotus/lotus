import {
    Button,
    Card,
    Col,
    Form,
    Input,
    InputNumber,
    Row, Select,
} from "antd";
// @ts-ignore
import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import {useMutation, useQueryClient, UseQueryResult} from "react-query";
import { toast } from "react-toastify";
import {BalanceAdjustment, Plan, PricingUnits} from "../api/api";
import { PageLayout } from "../components/base/PageLayout";
import {CreateBalanceAdjustmentType} from "../types/balance-adjustment";
import {useParams} from "react-router";
import { useQuery } from "react-query";
import {PricingUnit} from "../types/pricing-unit-type";
import PricingUnitDropDown from "../components/PricingUnitDropDown";
// @ts-ignore
import dayjs from "dayjs";
import { DatePicker } from 'antd';

type Params = {
    customerId: string;
};

const CreateCredit = () => {
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const queryClient = useQueryClient();
  const { customerId } = useParams<Params>();

  const { data , isLoading }: UseQueryResult<PricingUnit[]> = useQuery<PricingUnit[]>(
    ["pricing_unit_list"],
    () =>
      PricingUnits.list().then((res) => {
        return res;
      })
  );

  const disabledDate = (current) => {
  return current && current < dayjs().startOf('day');
};

  const mutation = useMutation(
    (post: CreateBalanceAdjustmentType) => BalanceAdjustment.createCredit(post),
    {
      onSuccess: () => {
        toast.success("Successfully created Credit", {
          position: toast.POSITION.TOP_CENTER,
        });
        form.resetFields();
        queryClient.invalidateQueries(["customer_list"]);
        navigate("/customers");
      },
      onError: () => {
        toast.error("Failed to create Credit", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
    }
  );

  const goBackPage = () => {
    navigate(-1);
  };

  const submit = () => {
    form
      .validateFields()
      .then((values) => {
        mutation.mutate({
            customer_id:customerId,
            amount:values.amount,
            amount_currency:values.amount_currency,
            description:values.description,
            pricing_unit_code: values.pricing_unit_code,
            effective_at:values.effective_at,
            expires_at:values.expires_at,
        });
        queryClient.invalidateQueries("balance_adjustments");
      })
      .catch((info) => {});
  };

  return (
    <PageLayout
      title="Create Credits"
      onBack={goBackPage}
      extra={[
        <Button
          key="create"
          onClick={() => form.submit()}
          size="large"
          type="primary"
        >
          Create new Credit
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
            expires_at: null
          }}
          onFinish={submit}
          autoComplete="off"
          labelCol={{ span: 8 }}
          wrapperCol={{ span: 16 }}
          labelAlign="left"
        >
          <Row gutter={[24, 24]}>
            <Col span={12}>
              <Row gutter={[24, 24]}>
                <Col span="24">
                  <Card title="Credit Information">
                    <Form.Item label="Description" name="description">
                      <Input
                        type="textarea"
                        placeholder="Description for adjustment"
                      />
                    </Form.Item>
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
                      <InputNumber defaultValue={0}  precision={2}/>
                    </Form.Item>
                      <Form.Item rules={[{required: true, message: "Please Select a currency"}]}
                          className="col-span-2"
                          name="pricing_unit_code"
                          label="Currency"
                      >
                          <PricingUnitDropDown setCurrentCurrency={value => form.setFieldValue("pricing_unit_code", value)}/>
                      </Form.Item>
                      <Form.Item
                          valuePropName='date'
                          rules={[{required: true, message: "Please Select a date"}]}
                          name="effective_at"
                          label="Effective At"
                      >
                          <DatePicker
                              defaultValue={dayjs(Date.now())}
                              disabledDate={disabledDate}
                              onChange={data => form.setFieldValue("effective_at", dayjs(data))}/>
                      </Form.Item>
                      <Form.Item
                          valuePropName='date'
                          name="expires_at"
                          label="Expires At"
                      >
                          <DatePicker disabledDate={disabledDate}
                                      onChange={data => form.setFieldValue("expires_at", dayjs(data))}/>
                      </Form.Item>
                  </Card>
                </Col>
              </Row>
            </Col>
          </Row>
        </Form>
      </Form.Provider>
    </PageLayout>
  );
};

export default CreateCredit;
