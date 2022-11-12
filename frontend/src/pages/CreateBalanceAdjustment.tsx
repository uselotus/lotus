import {
  Button,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  Row,
} from "antd";
// @ts-ignore
import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "react-query";
import { toast } from "react-toastify";
import {BalanceAdjustment} from "../api/api";
import { PageLayout } from "../components/base/PageLayout";
import {CreateBalanceAdjustmentType} from "../types/balance-adjustment";
import {useParams} from "react-router";

type Params = {
    customerId: string;
};

const CreateCredit = () => {
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const queryClient = useQueryClient();
  const { customerId } = useParams<Params>();

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
            description:values.description
        });
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
            amount_currency: "USD",
            description: "",
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
                      <InputNumber
                            addonBefore="$"
                            defaultValue={0}
                            precision={2}
                      />
                    </Form.Item>
                      <Form.Item label="currency" name="amount_currency">
                          <Input
                              placeholder="Ex: Add a currency"
                          />
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
