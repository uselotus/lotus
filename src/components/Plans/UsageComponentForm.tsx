import React, { useEffect, useState } from 'react'
import { Button, Checkbox, Form, Input, InputNumber, Modal, Radio, Select } from 'antd'
import './UsageComponentForm.css'
import { Metrics } from '../../api/api'
import { MetricNameType, MetricType } from '../../types/metric-type'

const { Option } = Select

type Props = {
  visible?: any
  onCancel: () => void
  componentsData: any
  handleComponentAdd: (s: any) => void
  editComponentItem: any
  setEditComponentsItem: (s: any) => void
}
function UsageComponentForm({
  handleComponentAdd,
  visible,
  onCancel,
  editComponentItem,
  setEditComponentsItem,
}: Props) {
  const [form] = Form.useForm()
  const [metrics, setMetrics] = useState<string[]>([])
  const [isFree, setIsFree] = useState(true)
  const [isLimit, setIsLimit] = useState(false)
  const initalData = editComponentItem ?? {
    cost_per_batch: 0.0,
    metric_units_per_batch: 1,
    free_amount: 0,
  }

  useEffect(() => {
    Metrics.getMetrics().then((res) => {
      const data = res
      if (data) {
        const metricList: string[] = []
        for (let i = 0; i < data.length; i++) {
          if (typeof data[i].billable_metric_name !== undefined) {
            metricList.push(data[i].billable_metric_name as unknown as string)
          }
        }
        setMetrics(metricList)
      }
    })
  }, [])

  return (
    <Modal
      visible={visible}
      title='Create Component'
      okText='Create'
      okType='default'
      cancelText='Cancel'
      width={700}
      onCancel={() => {
        onCancel()
        form.resetFields()
        setEditComponentsItem(undefined)
      }}
      onOk={() => {
        form
          .validateFields()
          .then((values) => {
            handleComponentAdd(values)
            onCancel()
          })
          .catch((info) => {
            console.log('Validate Failed:', info)
          })
          .finally(() => {
            form.resetFields()
          })
      }}
    >
      <Form form={form} layout='horizontal' name='component_form' initialValues={initalData}>
        <Form.Item
          name='metric'
          label='Metric'
          rules={[
            {
              required: true,
              message: 'Please select a metric',
            },
          ]}
        >
          <Select>
            {metrics?.map((metric_name) => (
              <Option value={metric_name}>{metric_name}</Option>
            ))}
          </Select>
        </Form.Item>
        <div className='grid grid-cols-2 space-x-4 my-4'>
          <Checkbox
            name='is_free'
            checked={!isFree}
            onChange={() => {
              setIsFree(!isFree)
              if (!isFree) {
                form.setFieldsValue({
                  free_amount: 0,
                })
              }
            }}
          >
            Charge For This Metric?
          </Checkbox>
          <Checkbox
            name='is_limit'
            checked={isLimit}
            onChange={() => {
              setIsLimit(!isLimit)
              if (isLimit) {
                form.setFieldsValue({ max_metric_units: 0 })
              }
            }}
          >
            Does This Metric Have A Limit?
          </Checkbox>
        </div>
        <div className='grid grid-cols-2 space-x-4 my-5'>
          <Form.Item name='free_amount' label='Free Units'>
            <InputNumber defaultValue={0} precision={5} disabled={isFree} />
          </Form.Item>
          <Form.Item name='max_metric_units' label='Max Amount'>
            <InputNumber precision={5} disabled={!isLimit} />
          </Form.Item>
        </div>
        {isFree ? null : (
          <div>
            <div className=' bg-grey3 mx-2 my-5'>
              <h3 className='py-2 px-3'>Tiers</h3>
            </div>
            <div className='flex flex-row items-center space-x-2'>
              <p>From</p>
              <Form.Item name='free_amount'>
                <InputNumber
                  defaultValue={0}
                  precision={4}
                  value={form.getFieldValue('free_amount')}
                  bordered={false}
                />
              </Form.Item>
              <p>To</p>
              <Form.Item name='max_metric_units'>
                <InputNumber
                  defaultValue={0}
                  precision={4}
                  disabled={!isLimit}
                  bordered={false}
                  value={form.getFieldValue('max_metric_units')}
                />
              </Form.Item>
              <p>, $</p>
              <Form.Item name='cost_per_batch'>
                <InputNumber defaultValue={0} precision={4} />
              </Form.Item>
              <p>Per</p>
              <Form.Item name='metric_units_per_batch'>
                <InputNumber defaultValue={1} precision={5} />
              </Form.Item>
              <p>Units</p>
            </div>
          </div>
        )}
      </Form>
    </Modal>
  )
}

export default UsageComponentForm
